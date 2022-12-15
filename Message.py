import asyncio
import os

from pyrogram.enums import MessageMediaType


def process_media(message):
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
    if message.forward_sender_name:
        author_name = message.forward_sender_name
        author_id = None
    elif message.forward_from_chat:
        author_name = message.forward_from_chat.title
        author_id = message.forward_from_chat.id
    else:
        author_name = message.chat.title
        author_id = -message.chat.id
    return author_id, author_name


async def download(message):
    return await message.download(
        file_name="static/tg_data/",
        progress=progress
    )


async def progress(current, total):
    """
    Show progress of media download.
    :param current: current size of a downloaded media
    :param total: total size of a downloading media
    :return:
    """
    print(f"{current * 100 / total:.1f}%")
