import asyncio
import os
from time import sleep

from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait


async def process_media(message):
    """
    Get media from the message and store it.
    :param message:
    :return:
    """
    attachment = None
    attachment_type = None
    if message.media:
        if message.media == MessageMediaType.WEB_PAGE:
            attachment = message.web_page.embed_url
            attachment_type = str(message.media)
        elif message.media == MessageMediaType.POLL:
            # TODO: extract poll data
            pass
        else:
            event_loop = asyncio.get_running_loop()
            if event_loop.is_running():
                task = asyncio.create_task(download(message))
                await task
                attachment = task.result()
            else:
                attachment = asyncio.run(download(message))
            attachment = os.path.basename(attachment)
            attachment_type = str(message.media)
    return attachment, attachment_type


def process_text(message):
    """
    Store message text into db.
    :param message:
    :return:
    """
    if message.text:
        text = message.text
    elif message.caption:
        text = message.caption
    else:
        text = None
    return text


def process_author(message):
    """
    Parse author of the message and store into db.
    :param message:
    :return:
    """
    author_photo = None
    if message.chat:
        if message.forward_sender_name:
            author_name = message.forward_sender_name
            author_id = None
        elif message.forward_from_chat:
            author_name = message.forward_from_chat.title
            author_id = message.forward_from_chat.id
        else:
            author_name = message.chat.title
            author_id = -message.chat.id
    else:
        author_id = 0
        author_name = ""
    return author_id, author_name, author_photo


async def download(message):
    # TODO: rewrite this so we'll have a queue of downloads
    result = None
    while not result:
        try:
            result = await message.download(file_name="static/tg_data/", progress=progress)
        except FloodWait as e:
            await asyncio.sleep(e.value)
    return result


async def progress(current, total):
    """
    Show progress of media download.
    :param current: current size of a downloaded media
    :param total: total size of a downloading media
    :return:
    """
    print(f"{current * 100 / total:.1f}%")
