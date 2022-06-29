#!/usr/bin/env python3
import json
import sqlite3

from pyrogram import Client
from pyrogram.raw.functions.channels import GetFullChannel
from pyrogram import filters
from pyrogram import enums
from pyrogram import raw
import sys, traceback
import asyncio
from datetime import datetime

from config import ACCOUNT, PHONE_NR, API_ID, API_HASH

app = Client(
    ACCOUNT,
    phone_number=PHONE_NR,
    api_id=API_ID,
    api_hash=API_HASH
)


async def main():
    async with app:
        async for dialog in app.get_dialogs():
            if dialog.chat.type == enums.ChatType.CHANNEL:
                print(dialog.chat.title or dialog.chat.first_name)
                print(dialog.chat.id)


async def download(message):
    await app.download_media(message, progress=progress)


@app.on_message(filters.channel)
def my_handler(client, message):
    conn = sqlite3.connect('tg.db')
    c = conn.cursor()
    print(message)
    db = open('db.txt', 'a')
    if message.media:
        try:
            asyncio.run(download(message))
        except:
            pass
    db.write(str(message))
    db.close()
    if message.text:
        text = message.text
    elif message.caption:
        text = message.caption
    else:
        text = None
    id = int(str(message.id)+str(-message.chat.id))
    if message.forward_sender_name:
        author_name = message.forward_sender_name
        author_id = None
    elif message.forward_from_chat:
        author_name = message.forward_from_chat.title
        author_id = message.forward_from_chat.id
    else:
        author_name = message.chat.title
        author_id = -message.chat.id
    c.execute('''INSERT INTO messages (id, message_text, author_id, author_name, sender_id, sender_name) VALUES (?, ?, ?, ?, ?, ?)''', (id, text, author_id, author_name, -message.chat.id, message.chat.title))
    conn.commit()


async def progress(current, total):
    print(f"{current * 100 / total:.1f}%")


conn = sqlite3.connect('tg.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS messages ([id] INTEGER PRIMARY KEY, [message_text] TEXT, [author_id] INTEGER, [author_name] TEXT, [sender_id] INTEGER, [sender_name] TEXT)''')
conn.commit()

app.run()