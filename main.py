#!/usr/bin/env python3
import sqlite3

from pyrogram import Client
from pyrogram import filters

from Message import process_media, process_text, process_author
from app import Message, db
from config import ACCOUNT, PHONE_NR, API_ID, API_HASH

app = Client(ACCOUNT, phone_number=PHONE_NR, api_id=API_ID, api_hash=API_HASH)


@app.on_message(filters.channel)
def my_handler(client, message):
    attachment, attachment_type = process_media(message)
    text = process_text(message)
    author_id, author_name = process_author(message)
    # TODO: if message_id exists in db, UPDATE message
    post = None
    if message.media_group_id:
        post = Message.query.order_by(Message.media_group_id).first()
    if post:
        if post.attachment_type:
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
                0
            )
        )
        db.session.commit()


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
        [media_group_id] TEXT,
        [read] INTEGER)"""
)
conn.commit()

app.run()
