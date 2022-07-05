#!/usr/bin/env python3
import os.path
import sqlite3

from pyrogram import Client
from pyrogram import filters
from pyrogram import enums
import asyncio

import db
from config import ACCOUNT, PHONE_NR, API_ID, API_HASH

app = Client(ACCOUNT, phone_number=PHONE_NR, api_id=API_ID, api_hash=API_HASH)


async def download(message):
    return await app.download_media(
        message,
        file_name="static/",
        progress=progress
    )


@app.on_message(filters.channel)
def my_handler(client, message):
    conn = sqlite3.connect("tg.db")
    c = conn.cursor()
    attachment = None
    attachment_type = None
    if message.media:
        try:
            attachment = asyncio.run(download(message))
            attachment = os.path.basename(attachment)
            attachment_type = str(message.media)
        except:
            pass
    if message.text:
        text = message.text
    elif message.caption:
        text = message.caption
    else:
        text = None
    id = int(str(message.id) + str(-message.chat.id))
    if message.forward_sender_name:
        author_name = message.forward_sender_name
        author_id = None
    elif message.forward_from_chat:
        author_name = message.forward_from_chat.title
        author_id = message.forward_from_chat.id
    else:
        author_name = message.chat.title
        author_id = -message.chat.id
    c.execute(
        """INSERT INTO messages
        (
            id,
            message_text,
            author_id,
            author_name,
            sender_id,
            sender_name,
            attachment_name,
            attachment_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            id,
            text,
            author_id,
            author_name,
            -message.chat.id,
            message.chat.title,
            attachment,
            attachment_type
        ),
    )
    conn.commit()


async def progress(current, total):
    print(f"{current * 100 / total:.1f}%")


db.init()

app.run()
