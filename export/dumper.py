#!/usr/bin/env python3
"""A module for dumping export data into the database"""
import json
import logging
import os.path
import sqlite3
import sys
import time
from base64 import b64encode
from datetime import UTC
from enum import Enum

import telethon.utils
from telethon.tl import types
from telethon.tl.types import *
from telethon.utils import get_peer_id, resolve_id, get_input_peer

from export import utils
from export.media import Media

logger = logging.getLogger(__name__)

DB_VERSION = 1


class InputFileType(Enum):
    """An enum to specify the type of InputFile"""

    NORMAL = 0
    DOCUMENT = 1


def sanitize_dict(dictionary):
    """
    Sanitizes a dictionary, encoding all bytes as
    Base64 so that it can be serialized as JSON.

    Assumes that there are no containers with bytes inside,
    and that the dictionary does not contain self-references.
    """
    for k, v in dictionary.items():
        if isinstance(v, bytes):
            dictionary[k] = str(b64encode(v), encoding="ascii")
        elif isinstance(v, datetime):
            dictionary[k] = v.timestamp()
        elif isinstance(v, dict):
            dictionary[k] = sanitize_dict(v)
        elif isinstance(v, list):
            result = []
            for d in v:
                if isinstance(d, dict):
                    result.append(sanitize_dict(d))
                else:
                    result.append(d)
            dictionary[k] = result
    return dictionary


class Dumper:
    """Class to interface with the database for exports"""

    def __init__(self, config):
        """
        Initialise the dumper. `config` should be a dict-like
        object from the config file"s Dumper section".
        """
        self.config = config
        if "DBFileName" in self.config:
            where = self.config["DBFileName"]
            if where != ":memory:":
                where = f"{os.path.join(self.config['OutputDirectory'], self.config['DBFileName'])}.db"
            self.conn = sqlite3.connect(where, check_same_thread=False)
        else:
            logger.error("A database filename is required!")
            exit()
        c = self.conn.cursor()

        self.chunk_size = max(int(config.get("ChunkSize", 100)), 1)
        self.max_chunks = max(int(config.get("MaxChunks", 0)), 0)
        self.invalidation_time = max(config.getint("InvalidationTime", 0), -1)

        self.dump_methods = (
            "message",
            "user",
            "message_service",
            "channel",
            "media",
            "forward",
        )

        self._dump_callbacks = {method: set() for method in self.dump_methods}

        c.execute(
            "SELECT name FROM sqlite_master " "WHERE type='table' AND name='Version'"
        )

        exists = bool(c.fetchone())
        if exists:
            c.execute("SELECT Version FROM Version")
            version = c.fetchone()
            if not version:
                c.execute("DROP TABLE IF EXISTS Version")
                exists = False
            elif version[0] != DB_VERSION:
                self._upgrade_database(old=version[0])
                self.conn.commit()
        if not exists:
            c.execute("CREATE TABLE Version (Version INTEGER)")
            c.execute("CREATE TABLE SelfInformation (UserID INTEGER)")
            c.execute("INSERT INTO Version VALUES (?)", (DB_VERSION,))

            c.execute(
                "CREATE TABLE Forward("
                "ID INTEGER PRIMARY KEY AUTOINCREMENT,"
                "OriginalDate INT NOT NULL,"
                "FromID INT,"
                "ChannelPost INT,"
                "PostAuthor TEXT)"
            )

            c.execute(
                "CREATE TABLE Media("
                "ID INTEGER PRIMARY KEY AUTOINCREMENT,"
                "Name TEXT,"
                "MimeType TEXT,"
                "Size INT,"
                "ThumbnailID INT,"
                "Type TEXT,"
                "LocalID INT,"
                "VolumeID INT,"
                "Secret INT,"
                "FileReference BLOB,"
                "AccessHash INT,"
                "MediaID INT,"
                "Extra TEXT,"
                "FOREIGN KEY (ThumbnailID) REFERENCES Media(ID))"
            )

            c.execute(
                "CREATE TABLE User("
                "ID INT NOT NULL,"
                "DateUpdated INT NOT NULL,"
                "FirstName TEXT NOT NULL,"
                "LastName TEXT,"
                "Username TEXT,"
                "Phone TEXT,"
                "Bio TEXT,"
                "Bot INTEGER,"
                "CommonChatsCount INT NOT NULL,"
                "PictureID INT,"
                "FOREIGN KEY (PictureID) REFERENCES Media(ID),"
                "PRIMARY KEY (ID, DateUpdated))"
            )

            c.execute(
                "CREATE TABLE Channel("
                "ID INT NOT NULL,"
                "DateUpdated INT NOT NULL,"
                "About TEXT,"
                "Title TEXT NOT NULL,"
                "Username TEXT,"
                "PictureID INT,"
                "PinMessageID INT,"
                "FOREIGN KEY (PictureID) REFERENCES Media(ID),"
                "PRIMARY KEY (ID, DateUpdated))"
            )

            c.execute(
                "CREATE TABLE Message("
                "ID INT NOT NULL,"
                "ContextID INT NOT NULL,"
                "Date INT NOT NULL,"
                "FromID INT,"
                "Message TEXT,"
                "ReplyMessageID INT,"
                "ForwardID INT,"
                "PostAuthor TEXT,"
                "ViewCount INT,"
                "MediaID INT,"
                "Formatting TEXT,"
                "ServiceAction TEXT,"
                "FOREIGN KEY (ForwardID) REFERENCES Forward(ID),"
                "FOREIGN KEY (MediaID) REFERENCES Media(ID),"
                "PRIMARY KEY (ID, ContextID))"
            )

            c.execute(
                "CREATE TABLE Resume("
                "ContextID INT NOT NULL,"
                "ID INT NOT NULL,"
                "Date INT NOT NULL,"
                "StopAt INT NOT NULL,"
                "PRIMARY KEY (ContextID))"
            )

            c.execute(
                "CREATE TABLE ResumeEntity("
                "ContextID INT NOT NULL,"
                "ID INT NOT NULL,"
                "AccessHash INT,"
                "PRIMARY KEY (ContextID, ID))"
            )

            c.execute(
                "CREATE TABLE ResumeMedia("
                "MediaID INT NOT NULL,"
                "ContextID INT NOT NULL,"
                "SenderID INT,"
                "Date INT,"
                "PRIMARY KEY (MediaID))"
            )
            self.conn.commit()

    def _upgrade_database(self, old):
        """
        This method knows how to migrate from old -> DB_VERSION.

        Currently, it performs no operation because this is the
        first version of the tables, in the future it should alter
        tables or somehow transfer the data between what changed.
        """

    # TODO make these callback functions less repetitive.

    def add_callback(self, dump_method, callback):
        """
        Add the callback function to the set of callbacks for the given
        dump method. dump_method should be a string, and callback should be a
        function which takes one argument - a tuple which will be dumped into
        the database. The list of valid dump methods is dumper.dump_methods.
        If the dumper does not dump a row due to the invalidation_time, the
        callback will still be called.
        """
        if dump_method not in self.dump_methods:
            raise ValueError(
                "Cannot attach callback to method {}. Available "
                "methods are {}".format(dump_method, self.dump_methods)
            )

        self._dump_callbacks[dump_method].add(callback)

    def remove_callback(self, dump_method, callback):
        """
        Remove the callback function from the set of callbacks for the given
        dump method. Will raise KeyError if the callback is not in the set of
        callbacks for that method
        """
        if dump_method not in self.dump_methods:
            raise ValueError(
                "Cannot remove callback from method {}. Available "
                "methods are {}".format(dump_method, self.dump_methods)
            )

        self._dump_callbacks[dump_method].remove(callback)

    def check_self_user(self, self_id):
        """
        Checks the self ID. If there is a stored ID, and it doesn't match the
        given one, an error message is printed and the application exits.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT UserID FROM SelfInformation")
        result = cur.fetchone()
        if result:
            if result[0] != self_id:
                print("This export database belongs to another user!", file=sys.stderr)
                exit(1)
        else:
            cur.execute("INSERT INTO SelfInformation VALUES (?)", (self_id,))
            self.commit()

    def dump_photo_size(self, media, row):
        row.type = "photo"
        row.mime_type = "image/jpeg"
        if isinstance(media, PhotoSizeEmpty):
            row.size = 0
        else:
            if isinstance(media, PhotoSize):
                row.size = media.size
            elif isinstance(media, PhotoCachedSize):
                row.size = len(media.bytes)
            if hasattr(media, "location"):
                if isinstance(media.location, InputFileLocation):
                    row = self.dump_input_file_location(media.location, row)
        return row

    def dump_input_file_location(self, media, row):
        row.local_id = media.local_id
        row.volume_id = media.volume_id
        row.secret = media.secret
        return row

    def dump_message_media_contact(self, media, row):
        row.type = "contact"
        row.name = f"{media.first_name} {media.last_name}"
        row.local_id = media.user_id
        try:
            row.secret = int(media.phone_number or "0")
        except ValueError:
            row.secret = 0
        return row

    def dump_message_media_document(self, media, row):
        row.type = utils.get_media_type(media)
        doc = media.document
        if isinstance(doc, Document):
            row.mime_type = doc.mime_type
            row.id = doc.id
            row.size = doc.size
            if doc.thumbs:
                row.thumbnail_id = self.dump_media(doc.thumbs[0])
            else:
                row.thumbnail_id = None
            row.local_id = doc.id
            row.file_reference = doc.file_reference
            row.access_hash = doc.access_hash
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    row.name = attr.file_name
        return row

    def dump_message_media_game(self, media, row):
        row.type = "game"
        game = media.game
        if isinstance(game, Game):
            row.name = game.short_name
            row.thumbnail_id = self.dump_media(game.photo)
            row.local_id = game.id
            row.secret = game.access_hash
        return row

    def dump_photo(self, media, row):
        row.type = "photo"
        row.mime_type = "image/jpeg"
        row.name = str(media.date)
        row.file_reference = media.file_reference
        row.access_hash = media.access_hash
        row.id = media.id
        sizes = [x for x in media.sizes if isinstance(x, (PhotoSize, PhotoCachedSize))]
        if sizes:
            small = min(sizes, key=lambda s: s.w * s.h)
            large = max(sizes, key=lambda s: s.w * s.h)
            self.dump_media(large)
            if small != large:
                row.thumbnail_id = self.dump_media(small, "thumbnail")
        return row

    def dump_message_media_geo(self, media, row):
        row.type = "geo"
        geo = media.geo
        if isinstance(geo, types.GeoPoint):
            row.name = f"({repr(geo.lat)}, {repr(geo.long)})"
        return row

    def dump_message_media_geo_live(self, media, row):
        row.type = "geolive"
        geo = media.geo
        if isinstance(geo, types.GeoPoint):
            row.name = f"({repr(geo.lat)}, {repr(geo.long)})"
        return row

    def dump_message_media_invoice(self, media, row):
        row.type = "invoice"
        row.name = media.title
        row.thumbnail_id = self.dump_media(media.photo)
        return row

    def dump_message_media_photo(self, media, row):
        row.type = "photo"
        row.mime_type = "image/jpeg"
        row = self.dump_photo(media.photo, row)
        return row

    def dump_message_media_venue(self, media, row):
        row.type = "venue"
        row.name = f"{media.title} - {media.address} ({media.provider}, {media.venue_id} {media.venue_type})"
        geo = media.geo
        if isinstance(geo, types.GeoPoint):
            row.name += f" at ({repr(geo.lat)}, {repr(geo.long)})"
        return row

    def dump_message_media_web_page(self, media, row):
        row.type = "webpage"
        web = media.webpage
        if isinstance(web, types.WebPage):
            row.name = web.title
            row.thumbnail_id = self.dump_media(web.photo, "thumbnail")
            row.local_id = web.id
            row.secret = web.hash
        return row

    def dump_user_profile_photo(self, media, row):
        row.type = "photo"
        row.mime_type = "image/jpeg"
        row.thumbnail_id = self.dump_media(media.photo_small, "thumbnail")
        self.dump_media(media.photo_big)
        return row

    def dump_message(self, message, context_id, forward_id, media_id):
        """
        Dump a Message into the Message table.

        Params:
            Message to dump,
            ID of the chat dumping,
            ID of Forward in the DB (or None),
            ID of message Media in the DB (or None)

        Returns:
            Inserted row ID.
        """
        if not message.message and message.media:
            message.message = getattr(message.media, "caption", "")

        row = (
            message.id,
            context_id,
            message.date.timestamp(),
            message.from_id,
            message.message,
            message.reply_to_msg_id,
            forward_id,
            message.post_author,
            message.views,
            media_id,
            utils.encode_msg_entities(message.entities),
            None,
        )

        for callback in self._dump_callbacks["message"]:
            callback(row)

        return self._insert("Message", row)

    def dump_message_service(self, message, context_id, media_id):
        """Similar to self.dump_message, but for MessageAction's."""
        name = utils.action_to_name(message.action)
        if not name:
            return

        extra = message.action.to_dict()
        del extra["_"]
        extra = json.dumps(sanitize_dict(extra))

        row = (
            message.id,
            context_id,
            message.date.timestamp(),
            message.from_id,
            extra,
            message.reply_to_msg_id,
            None,
            None,
            None,
            media_id,
            None,
            name,
        )

        for callback in self._dump_callbacks["message_service"]:
            callback(row)

        return self._insert("Message", row)

    def dump_user(self, user_full, photo_id, timestamp=None):
        """Dump a UserFull into the User table
        Params: UserFull to dump, MediaID of the profile photo in the DB
        Returns -, or False if not added"""
        values = (
            user_full.user.id,
            timestamp or round(time.time()),
            user_full.user.first_name,
            user_full.user.last_name,
            user_full.user.username,
            user_full.user.phone,
            user_full.about,
            user_full.user.bot,
            user_full.common_chats_count,
            photo_id,
        )

        for callback in self._dump_callbacks["user"]:
            callback(values)

        return self._insert_if_valid_date(
            "User", values, date_column=1, where=("ID", user_full.user.id)
        )

    def dump_channel(self, channel_full, channel, photo_id, timestamp=None):
        """Dump a Channel into the Channel table.
        Params: ChannelFull, Channel to dump, MediaID
                of the profile photo in the DB
        Returns -"""
        values = (
            get_peer_id(channel),
            timestamp or round(time.time()),
            channel_full.about,
            channel.title,
            channel.username,
            photo_id,
            channel_full.pinned_msg_id,
        )

        for callback in self._dump_callbacks["channel"]:
            callback(values)

        return self._insert_if_valid_date(
            "Channel", values, date_column=1, where=("ID", get_peer_id(channel))
        )

    def dump_media(self, media, media_type=None):
        """Dump a MessageMedia into the Media table
        Params: media Telethon object
        Returns: ID of inserted row"""
        if not media:
            return

        row = Media()
        row.type = media_type
        row.extra = json.dumps(sanitize_dict(media.to_dict()))

        if isinstance(media, (MessageMediaEmpty, MessageMediaUnsupported, PhotoEmpty)):
            return
        elif isinstance(media, MessageMediaContact):
            row = self.dump_message_media_contact(media, row)
        elif isinstance(media, MessageMediaDocument):
            row = self.dump_message_media_document(media, row)
        elif isinstance(media, MessageMediaGame):
            row = self.dump_message_media_game(media, row)
        elif isinstance(media, MessageMediaGeo):
            row = self.dump_message_media_geo(media, row)
        elif isinstance(media, MessageMediaGeoLive):
            row = self.dump_message_media_geo_live(media, row)
        elif isinstance(media, MessageMediaInvoice):
            row = self.dump_message_media_invoice(media, row)
        elif isinstance(media, MessageMediaPhoto):
            row = self.dump_message_media_photo(media, row)
        elif isinstance(media, MessageMediaVenue):
            row = self.dump_message_media_venue(media, row)
        elif isinstance(media, MessageMediaWebPage):
            row = self.dump_message_media_web_page(media, row)
        elif isinstance(media, types.Photo):
            row = self.dump_photo(media, row)
        elif isinstance(media, (PhotoSize, PhotoCachedSize, PhotoSizeEmpty)):
            row = self.dump_photo_size(media, row)
        elif isinstance(media, (UserProfilePhoto, ChatPhoto)):
            row = self.dump_user_profile_photo(media, row)
        elif isinstance(media, InputFileLocation):
            row = self.dump_input_file_location(media, row)
        return self.commit_media(row)

    def commit_media(self, row):
        if row.type:
            for callback in self._dump_callbacks["media"]:
                callback(row)

            c = self.conn.cursor()
            c.execute(
                "SELECT ID FROM Media WHERE LocalID = ? "
                "AND VolumeID = ? AND Secret = ?",
                (row.local_id, row.volume_id, row.secret),
            )
            existing_row = c.fetchone()
            if existing_row:
                return existing_row[0]
            c.execute("SELECT ID FROM Media WHERE AccessHash = ? ", (row.access_hash,))
            existing_row = c.fetchone()
            if existing_row:
                return existing_row[0]

            return self._insert(
                "Media",
                (
                    None,
                    row.name,
                    row.mime_type,
                    row.size,
                    row.thumbnail_id,
                    row.type,
                    row.local_id,
                    row.volume_id,
                    row.secret,
                    row.file_reference,
                    row.access_hash,
                    row.id,
                    row.extra,
                ),
            )

    def dump_forward(self, forward):
        """
        Dump a message forward relationship into the Forward table.

        Params: MessageFwdHeader Telethon object
        Returns: ID of inserted row"""
        if not forward:
            return None

        try:
            from_id = forward.from_id.channel_id
        except AttributeError:
            try:
                from_id = forward.from_id.user_id
            except AttributeError:
                try:
                    from_id = forward.from_name
                except AttributeError:
                    raise
        row = (
            None,
            forward.date.timestamp(),
            # TODO: who is responsible for this number?
            from_id,
            forward.channel_post,
            forward.post_author,
        )

        for callback in self._dump_callbacks["forward"]:
            callback(row)

        return self._insert("Forward", row)

    def get_max_message_id(self, context_id):
        """
        Returns the largest saved message ID for the given
        context_id, or 0 if no messages have been saved.
        """
        row = self.conn.execute(
            "SELECT MAX(ID) FROM Message WHERE " "ContextID = ?", (context_id,)
        ).fetchone()
        return row[0] if row else 0

    def get_message_count(self, context_id):
        """Gets the message count for the given context"""
        tuple_ = self.conn.execute(
            "SELECT COUNT(*) FROM MESSAGE WHERE ContextID = ?", (context_id,)
        ).fetchone()
        return tuple_[0] if tuple_ else 0

    def get_resume(self, context_id):
        """
        For the given context ID, return a tuple consisting of the offset
        ID and offset date from which to continue, as well as at which ID
        to stop.
        """
        c = self.conn.execute(
            "SELECT ID, Date, StopAt FROM Resume WHERE " "ContextID = ?", (context_id,)
        )
        return c.fetchone() or (0, 0, 0)

    def save_resume(self, context_id, msg=0, msg_date=0, stop_at=0):
        """
        Saves the information required to resume a download later.
        """
        if isinstance(msg_date, datetime):
            msg_date = int(msg_date.timestamp())

        return self._insert("Resume", (context_id, msg, msg_date, stop_at))

    def iter_resume_entities(self, context_id):
        """
        Returns an iterator over the entities that need resuming for the
        given context_id. Note that the entities are *removed* once the
        iterator is consumed completely.
        """
        c = self.conn.execute(
            "SELECT ID, AccessHash FROM ResumeEntity " "WHERE ContextID = ?",
            (context_id,),
        )
        row = c.fetchone()
        while row:
            kind = resolve_id(row[0])[1]
            if kind == types.PeerUser:
                yield types.InputPeerUser(row[0], row[1])
            elif kind == types.PeerChat:
                yield types.InputPeerChat(row[0])
            elif kind == types.PeerChannel:
                yield types.InputPeerChannel(row[0], row[1])
            row = c.fetchone()

        c.execute("DELETE FROM ResumeEntity WHERE ContextID = ?", (context_id,))

    def save_resume_entities(self, context_id, entities):
        """
        Saves the given entities for resuming at a later point.
        """
        rows = []
        for ent in entities:
            ent = get_input_peer(ent)
            if isinstance(ent, types.InputPeerUser):
                rows.append((context_id, ent.user_id, ent.access_hash))
            elif isinstance(ent, types.InputPeerChat):
                rows.append((context_id, ent.chat_id, None))
            elif isinstance(ent, types.InputPeerChannel):
                rows.append((context_id, ent.channel_id, ent.access_hash))
        c = self.conn.cursor()
        c.executemany("INSERT OR REPLACE INTO ResumeEntity " "VALUES (?,?,?)", rows)

    def iter_resume_media(self, context_id):
        """
        Returns an iterator over the media tuples that need resuming for
        the given context_id. Note that the media rows are *removed* once
        the iterator is consumed completely.
        """
        c = self.conn.execute(
            "SELECT MediaID, SenderID, Date " "FROM ResumeMedia WHERE ContextID = ?",
            (context_id,),
        )
        row = c.fetchone()
        while row:
            media_id, sender_id, date = row
            yield media_id, sender_id, datetime.fromtimestamp(date, UTC)
            row = c.fetchone()

        c.execute("DELETE FROM ResumeMedia WHERE ContextID = ?", (context_id,))

    def save_resume_media(self, media_tuples):
        """
        Saves the given media tuples for resuming at a later point.

        The tuples should consist of four elements, these being
        ``(media_id, context_id, sender_id, date)``.
        """
        self.conn.executemany(
            "INSERT OR REPLACE INTO ResumeMedia " "VALUES (?,?,?,?)", media_tuples
        )

    def _insert_if_valid_date(self, into, values, date_column, where):
        """
        Helper method to self._insert(into, values) after checking that the
        given values are different from the latest dump or that the delta
        between the current date and the existing column date_column is
        bigger than the invalidation time. `where` is used to get the last
        dumped item to check for invalidation time.

        As an example, ("ID", 4) -> WHERE ID = ?, 4
        """
        last = self.conn.execute(
            "SELECT * FROM {} WHERE {} = ? ORDER BY DateUpdated DESC".format(
                into, where[0]
            ),
            (where[1],),
        ).fetchone()

        if last:
            delta = values[date_column] - last[date_column]

            if len(values) != len(last):
                raise TypeError("values has a different number of columns to table")
            rows_same = True
            for i, val in enumerate(values):
                if i != date_column and val != last[i]:
                    rows_same = False

            if delta < self.invalidation_time and rows_same:
                return False
        return self._insert(into, values)

    def _insert(self, into, values):
        """
        Helper method to insert or replace the
        given tuple of values into the given table.
        """
        try:
            fmt = ",".join("?" * len(values))
            c = self.conn.execute(
                "INSERT OR REPLACE INTO {} VALUES ({})".format(into, fmt), values
            )
            return c.lastrowid
        except sqlite3.IntegrityError as error:
            self.conn.rollback()
            logger.error("Integrity error: %s", str(error))
            raise

    def commit(self):
        """
        Commits the changes made to the database to persist on disk.
        """
        self.conn.commit()
