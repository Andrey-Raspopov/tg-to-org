#!/bin/env python3
import asyncio
import datetime
import itertools
import logging
import os
import time
from collections import defaultdict

import tqdm
from telethon import utils
from telethon.errors import ChatAdminRequiredError
from telethon.tl import types, functions

from . import utils as export_utils

__log__ = logging.getLogger(__name__)

VALID_TYPES = {"photo", "document", "video", "audio", "sticker", "voice", "chatphoto"}
BAR_FORMAT = (
    "{l_bar}{bar}| {n_fmt}/{total_fmt} "
    "[{elapsed}<{remaining}, {rate_noinv_fmt}{postfix}]"
)

QUEUE_TIMEOUT = 5
DOWNLOAD_PART_SIZE = 256 * 1024

USER_FULL_DELAY = 1.5
CHAT_FULL_DELAY = 1.5
MEDIA_DELAY = 3.0
HISTORY_DELAY = 1.0


class Downloader:
    """
    Download dialogs and their associated data, and dump them.
    Make Telegram API requests and sleep for the appropriate time.
    """

    def __init__(self, client, config, dumper, loop):
        self.client = client
        self.loop = loop or asyncio.get_event_loop()
        self.max_size = config.getint("MaxSize")
        self.types = {
            x.strip().lower()
            for x in (config.get("MediaWhitelist") or "").split(",")
            if x.strip()
        }
        self.media_fmt = os.path.join(
            config["OutputDirectory"], config["MediaFilenameFmt"]
        )
        assert all(x in VALID_TYPES for x in self.types)
        if self.types:
            self.types.add("unknown")

        self.dumper = dumper
        self._checked_entity_ids = set()
        self._media_bar = None

        self._displays = {}

        self._incomplete_download = None

        self._media_queue = asyncio.Queue()
        self._user_queue = asyncio.Queue()
        self._chat_queue = asyncio.Queue()
        self._running = False

    def _check_media(self, media):
        """
        Checks whether the given MessageMedia should be downloaded or not.
        """
        if not media or not self.max_size:
            return False
        if not self.types:
            # TODO: white or blacklist?
            return False
        return export_utils.get_media_type(media) in self.types

    def _dump_full_entity(self, entity):
        """
        Dumps the full entity into the Dumper, also enqueuing their profile
        photo if any, so it can be downloaded later by a different coroutine.
        Supply None as the photo_id if self.types is empty or 'chatphoto' is
        not in self.types
        """
        if isinstance(entity, types.UserFull):
            if not self.types or "chatphoto" in self.types:
                photo_id = self.dumper.dump_media(entity.profile_photo)
            else:
                photo_id = None
            self.enqueue_photo(entity.profile_photo, photo_id, entity.user)
            self.dumper.dump_user(entity, photo_id=photo_id)

        elif isinstance(entity, types.messages.ChatFull):
            if not self.types or "chatphoto" in self.types:
                photo_id = self.dumper.dump_media(entity.full_chat.chat_photo)
            else:
                photo_id = None
            chat = next(x for x in entity.chats if x.id == entity.full_chat.id)
            self.enqueue_photo(entity.full_chat.chat_photo, photo_id, chat)
            self.dumper.dump_channel(entity.full_chat, chat, photo_id)

    def _dump_messages(self, messages, target):
        """
        Helper method to iterate the messages from a GetMessageHistoryRequest
        and dump them into the Dumper, mostly to avoid excessive nesting.

        Also, enqueues any media to be downloaded later by a different coroutine.
        """
        for m in messages:
            if isinstance(m, types.Message):
                media_id = self.dumper.dump_media(m.media)
                if media_id and self._check_media(m.media):
                    self.enqueue_media(
                        media_id, utils.get_peer_id(target), m.from_id, m.date
                    )

                self.dumper.dump_message(
                    message=m,
                    context_id=utils.get_peer_id(target),
                    forward_id=self.dumper.dump_forward(m.fwd_from),
                    media_id=media_id,
                )
            elif isinstance(m, types.MessageService):
                if isinstance(m.action, types.MessageActionChatEditPhoto):
                    media_id = self.dumper.dump_media(m.action.photo)
                    self.enqueue_photo(
                        m.action.photo, media_id, target, peer_id=m.from_id, date=m.date
                    )
                else:
                    media_id = None
                self.dumper.dump_message_service(
                    message=m, context_id=utils.get_peer_id(target), media_id=media_id
                )

    def _get_name(self, peer_id):
        if peer_id is None:
            return ""

        name = self._displays.get(peer_id)
        if name:
            return name

        c = self.dumper.conn.cursor()
        _, kind = utils.resolve_id(peer_id)
        if kind == types.PeerUser:
            row = c.execute(
                "SELECT FirstName, LastName FROM User " "WHERE ID = ?", (peer_id,)
            ).fetchone()
            if row:
                return "{} {}".format(row[0] or "", row[1] or "").strip()
        elif kind == types.PeerChannel:
            row = c.execute(
                "SELECT Title FROM Channel " "WHERE ID = ?", (peer_id,)
            ).fetchone()
            if row:
                return row[0]
        return ""

    async def _download_media(self, media_id, context_id, sender_id, date, bar):
        media_row = self.dumper.conn.execute(
            "SELECT LocalID, VolumeID, Secret, Type, MimeType, Name, Size, FileReference, MediaID, AccessHash "
            "FROM Media WHERE ID = ?",
            (media_id,),
        ).fetchone()
        media_type = media_row[3].split(".")
        media_type, media_subtype = media_type[0], media_type[-1]
        if media_type not in ("photo", "document", "video"):
            return

        formatter = defaultdict(
            str,
            context_id=context_id,
            sender_id=sender_id,
            type=media_subtype or "unknown",
            name=self._get_name(context_id) or "unknown",
            sender_name=self._get_name(sender_id) or "unknown",
        )

        ext = None
        filename = media_row[5]
        if filename:
            filename, ext = os.path.splitext(filename)
        else:
            filename = date.strftime(f"{formatter['type']}_%Y-%m-%d_%H-%M-%S")

        if not ext:
            ext = export_utils.get_extension(media_row[4])

        formatter["filename"] = filename
        filename = date.strftime(self.media_fmt).format_map(formatter)
        filename += f".{media_id}{ext}"
        if os.path.isfile(filename):
            __log__.debug("Skipping already-existing file %s", filename)
            return

        __log__.debug("Downloading to %s", filename)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        if media_type in ["photo"]:
            location = types.InputPhotoFileLocation(
                id=media_row[8],
                access_hash=media_row[9],
                file_reference=media_row[7],
                thumb_size="y",
            )
        elif media_type in ["document"]:
            location = types.InputDocumentFileLocation(
                id=media_row[8],
                access_hash=media_row[9],
                file_reference=media_row[7],
                thumb_size="-1",
            )
        else:
            location = types.InputFileLocation(
                local_id=media_row[0],
                volume_id=media_row[1],
                secret=media_row[2],
                file_reference=media_row[7],
            )

        def progress(saved, total):
            """Increment the tqdm progress bar"""
            if total is None:
                bar.total += saved
                bar.update(saved)
            elif saved == total:
                mod = (saved % DOWNLOAD_PART_SIZE) or DOWNLOAD_PART_SIZE
                bar.update(mod)
            else:
                bar.update(DOWNLOAD_PART_SIZE)

        if media_row[6] is not None:
            bar.total += media_row[6]

        self._incomplete_download = filename
        try:
            await self.client.download_file(
                location,
                file=filename,
                file_size=media_row[6],
                part_size_kb=DOWNLOAD_PART_SIZE // 1024,
                progress_callback=progress,
            )
        except Exception as e:
            print("atatat")
            print(e)
        self._incomplete_download = None

    async def _media_consumer(self, queue, bar):
        while self._running:
            start = time.time()
            media_id, context_id, sender_id, date = await queue.get()
            try:
                await self._download_media(
                    media_id,
                    context_id,
                    sender_id,
                    datetime.datetime.fromtimestamp(date, datetime.UTC),
                    bar,
                )
            except Exception as e:
                print("atata")
                print(e)
                pass
            queue.task_done()
            await asyncio.sleep(max(MEDIA_DELAY - (time.time() - start), 0))

    async def _user_consumer(self, queue, bar):
        while self._running:
            start = time.time()
            try:
                self._dump_full_entity(
                    await self.client(
                        functions.users.GetFullUserRequest(await queue.get())
                    )
                )
            except:
                print("trututu")
            queue.task_done()
            bar.update(1)
            await asyncio.sleep(max(USER_FULL_DELAY - (time.time() - start), 0))

    async def _chat_consumer(self, queue, bar):
        while self._running:
            start = time.time()
            chat = await queue.get()
            if isinstance(chat, (types.Chat, types.PeerChat)):
                self._dump_full_entity(chat)
            else:
                try:
                    self._dump_full_entity(
                        await self.client(
                            functions.channels.GetFullChannelRequest(chat)
                        )
                    )
                except:
                    print("tratata")
            queue.task_done()
            bar.update(1)
            await asyncio.sleep(max(CHAT_FULL_DELAY - (time.time() - start), 0))

    def enqueue_entities(self, entities):
        """
        Enqueues the given iterable of entities to be dumped later by a
        different coroutine. These in turn might enqueue profile photos.
        """
        for entity in entities:
            eid = utils.get_peer_id(entity)
            self._displays[eid] = utils.get_display_name(entity)
            if isinstance(entity, types.User):
                if entity.deleted or entity.min:
                    continue
            elif isinstance(entity, types.Channel):
                if entity.left:
                    continue
            elif not isinstance(
                entity,
                (
                    types.Chat,
                    types.InputPeerUser,
                    types.InputPeerChat,
                    types.InputPeerChannel,
                ),
            ):
                continue

            if eid in self._checked_entity_ids:
                continue
            else:
                self._checked_entity_ids.add(eid)
                if isinstance(entity, (types.User, types.InputPeerUser)):
                    self._user_queue.put_nowait(entity)
                else:
                    self._chat_queue.put_nowait(entity)

    def enqueue_media(self, media_id, context_id, sender_id, date):
        """
        Enqueues the given message or media from the given context entity
        to be downloaded later. If the ID of the message is known it should
        be set in known_id. The media won't be enqueued unless its download
        is desired.
        """
        if not date:
            date = int(time.time())
        elif not isinstance(date, int):
            date = int(date.timestamp())
        self._media_queue.put_nowait((media_id, context_id, sender_id, date))

    def enqueue_photo(self, photo, photo_id, context, peer_id=None, date=None):
        if not photo_id:
            return
        if not isinstance(context, int):
            context = utils.get_peer_id(context)
        if peer_id is None:
            peer_id = context
        if date is None:
            date = getattr(photo, "date", None) or datetime.datetime.now()
        self.enqueue_media(photo_id, context, peer_id, date)

    async def start(self, target_id):
        """
        Starts the dump with the given target ID.
        """
        self._running = True
        self._incomplete_download = None
        target_in = await self.client.get_input_entity(target_id)
        target = await self.client.get_entity(target_in)
        target_id = utils.get_peer_id(target)

        found = self.dumper.get_message_count(target_id)
        chat_name = utils.get_display_name(target)
        msg_bar = tqdm.tqdm(
            unit=" messages", desc=chat_name, initial=found, bar_format=BAR_FORMAT
        )
        ent_bar = tqdm.tqdm(
            unit=" entities",
            desc="entities",
            bar_format=BAR_FORMAT,
            postfix={"chat": chat_name},
        )
        med_bar = tqdm.tqdm(
            unit="B",
            desc="media",
            unit_divisor=1000,
            unit_scale=True,
            bar_format=BAR_FORMAT,
            total=0,
            postfix={"chat": chat_name},
        )

        asyncio.ensure_future(
            self._user_consumer(self._user_queue, ent_bar), loop=self.loop
        )
        asyncio.ensure_future(
            self._chat_consumer(self._chat_queue, ent_bar), loop=self.loop
        )
        asyncio.ensure_future(
            self._media_consumer(self._media_queue, med_bar), loop=self.loop
        )

        self.enqueue_entities(self.dumper.iter_resume_entities(target_id))
        for mid, sender_id, date in self.dumper.iter_resume_media(target_id):
            self.enqueue_media(mid, target_id, sender_id, date)

        try:
            self.enqueue_entities((target,))
            ent_bar.total = len(self._checked_entity_ids)
            req = functions.messages.GetHistoryRequest(
                peer=target_in,
                offset_id=0,
                offset_date=None,
                add_offset=0,
                limit=self.dumper.chunk_size,
                max_id=0,
                min_id=0,
                hash=0,
            )

            req.offset_id, req.offset_date, stop_at = self.dumper.get_resume(target_id)
            if req.offset_id:
                __log__.info("Resuming at %s (%s)", req.offset_date, req.offset_id)

            chunks_left = self.dumper.max_chunks
            while self._running:
                start = time.time()
                history = await self.client(req)
                self.enqueue_entities(itertools.chain(history.users, history.chats))
                ent_bar.total = len(self._checked_entity_ids)

                self._dump_messages(history.messages, target)

                count = len(history.messages)
                msg_bar.total = getattr(history, "count", count)
                msg_bar.update(count)
                if history.messages:
                    found = min(found + len(history.messages), msg_bar.total)
                    req.offset_id = min(m.id for m in history.messages)
                    req.offset_date = min(m.date for m in history.messages)

                if count < req.limit or req.offset_id <= stop_at:
                    __log__.debug("Received less messages than limit, done.")
                    max_id = self.dumper.get_max_message_id(target_id) or 0
                    self.dumper.save_resume(target_id, stop_at=max_id)
                    break

                self.dumper.save_resume(
                    target_id,
                    msg=req.offset_id,
                    msg_date=req.offset_date,
                    stop_at=stop_at,
                )
                self.dumper.commit()

                chunks_left -= 1
                if chunks_left == 0:
                    __log__.debug("Reached maximum amount of chunks, done.")
                    break

                await asyncio.sleep(max(HISTORY_DELAY - (time.time() - start), 0))

            msg_bar.n = msg_bar.total
            msg_bar.close()
            self.dumper.commit()

            __log__.info(
                "Done. Retrieving full information about %s missing entities.",
                self._user_queue.qsize() + self._chat_queue.qsize(),
            )
            await self._user_queue.join()
            await self._chat_queue.join()
            await self._media_queue.join()
        finally:
            self._running = False
            ent_bar.n = ent_bar.total
            ent_bar.close()
            med_bar.n = med_bar.total
            med_bar.close()
            entities = []
            while not self._user_queue.empty():
                entities.append(self._user_queue.get_nowait())
            while not self._chat_queue.empty():
                entities.append(self._chat_queue.get_nowait())
            if entities:
                self.dumper.save_resume_entities(target_id, entities)

            media = []
            while not self._media_queue.empty():
                media.append(self._media_queue.get_nowait())
            self.dumper.save_resume_media(media)

            if entities or media:
                self.dumper.commit()

            if self._incomplete_download is not None and os.path.isfile(
                self._incomplete_download
            ):
                os.remove(self._incomplete_download)

    async def download_past_media(self, dumper, target_id):
        """
        Downloads the past media that has already been dumped into the
        database but has not been downloaded for the given target ID yet.

        Media which formatted filename results in an already-existing file
        will be *ignored* and not re-downloaded again.
        """
        # TODO Should this respect and download only allowed media? Or all?
        target_in = await self.client.get_input_entity(target_id)
        target = await self.client.get_entity(target_in)
        target_id = utils.get_peer_id(target)
        bar = tqdm.tqdm(
            unit="B",
            desc="media",
            unit_divisor=1000,
            unit_scale=True,
            bar_format=BAR_FORMAT,
            total=0,
            postfix={"chat": utils.get_display_name(target)},
        )

        msg_cursor = dumper.conn.cursor()
        msg_cursor.execute(
            "SELECT ID, Date, FromID, MediaID FROM Message "
            "WHERE ContextID = ? AND MediaID IS NOT NULL",
            (target_id,),
        )

        msg_row = msg_cursor.fetchone()
        while msg_row:
            try:

                await self._download_media(
                    media_id=msg_row[3],
                    context_id=target_id,
                    sender_id=msg_row[2],
                    date=datetime.datetime.fromtimestamp(msg_row[1], datetime.UTC),
                    bar=bar,
                )
            except Exception as e:
                print("no")
                print(e)
            msg_row = msg_cursor.fetchone()
