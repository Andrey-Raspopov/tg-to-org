#!/usr/bin/env python3
import os.path
import sqlite3

import asyncio
from pyrogram import Client
from pyrogram import filters

from app import Message, db
from config import ACCOUNT, PHONE_NR, API_ID, API_HASH

app = Client(ACCOUNT, phone_number=PHONE_NR, api_id=API_ID, api_hash=API_HASH)


async def download(message):
    return await message.download(
        file_name="static/tg_data/",
        progress=progress
    )


@app.on_message(filters.channel)
def my_handler(client, message):
    attachment = None
    attachment_type = None
    if message.media:
        try:
            attachment = asyncio.run(download(message))
            attachment = os.path.basename(attachment)
            attachment_type = str(message.media)
        except:
            # TODO: find out exception types for this shit
            # TODO: Work with polls
            pass
    if message.text:
        text = message.text
    elif message.caption:
        text = message.caption
    else:
        text = None
    if message.forward_sender_name:
        author_name = message.forward_sender_name
        author_id = None
    elif message.forward_from_chat:
        author_name = message.forward_from_chat.title
        author_id = message.forward_from_chat.id
    else:
        author_name = message.chat.title
        author_id = -message.chat.id
    # TODO: if message_id exists in db, UPDATE message
    post = None
    if message.media_group_id:
        post = Message.query.order_by(Message.media_group_id).first()
    if post:
        post.attachment_type += f";{attachment_type}"
        post.attachment_name += f";{attachment}"
        db.session.commit()
    else:
        db.session.add(
            Message(
                text,
                author_id,
                author_name,
                -message.chat.id,
                message.chat.title,
                attachment,
                attachment_type,
                str(message.date),
                message.media_group_id,
            )
        )
        db.session.commit()


async def progress(current, total):
    """
    Show progress of media download.
    :param current: current size of a downloaded media
    :param total: total size of a downloading media
    :return:
    """
    print(f"{current * 100 / total:.1f}%")


conn = sqlite3.connect("tg.db")
c = conn.cursor()
c.execute(
    """CREATE TABLE IF NOT EXISTS messages
        ([id] INTEGER PRIMARY KEY,
        [message_text] TEXT,
        [author_id] INTEGER,
        [author_name] TEXT,
        [sender_id] INTEGER,
        [sender_name] TEXT,
        [attachment_name] TEXT,
        [attachment_type] TEXT,
        [date] TEXT,
        [media_group_id] TEXT)"""
)
conn.commit()

app.run()
