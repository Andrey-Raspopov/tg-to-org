#!/usr/bin/env python3

from pyrogram import Client
from pyrogram import filters

from Message import process_media, process_text, process_author
from app import app as flask_app
from app import db
from config import ACCOUNT, PHONE_NR, API_ID, API_HASH
from models.message import Message

app = Client(ACCOUNT, phone_number=PHONE_NR, api_id=API_ID, api_hash=API_HASH)


@app.on_message(filters.channel)
async def my_handler(_, message):
    attachment, attachment_type = await process_media(message)
    text = process_text(message)
    author_id, author_name, author_photo = process_author(message)
    # TODO: if message_id exists in db, UPDATE message
    post = None
    if message.media_group_id:
        with flask_app.app_context():
            post = Message.query.order_by(Message.media_group_id).first()
    if post:
        if post.attachment_type:
            post.attachment_type += f";{attachment_type}"
            post.attachment_name += f";{attachment}"
        with flask_app.app_context():
            db.session.commit()
    else:
        with flask_app.app_context():
            db.session.add(
                Message(
                    message.id,
                    text,
                    author_id,
                    author_name,
                    -message.chat.id,
                    message.chat.title,
                    attachment,
                    attachment_type,
                    str(message.date),
                    message.media_group_id,
                    0,
                    author_photo
                )
            )
            db.session.commit()


async def get_messages(channel):
    async with app:
        for i in range(1, 13476):
            message = await app.get_messages(channel, i)
            if message.empty:
                continue
            attachment, attachment_type = None, None # await process_media(message)
            text = process_text(message)
            author_id, author_name = process_author(message)
            # TODO: if message_id exists in db, UPDATE message
            post = None
            if message.media_group_id:
                with flask_app.app_context():
                    post = Message.query.order_by(Message.media_group_id).first()
            if post:
                if post.attachment_type:
                    post.attachment_type += f";{attachment_type}"
                    post.attachment_name += f";{attachment}"
                with flask_app.app_context():
                    db.session.commit()
            else:
                with flask_app.app_context():
                    db.session.add(
                        Message(
                            message.id,
                            text,
                            author_id,
                            author_name,
                            -message.chat.id if message.chat else 0,
                            message.chat.title if message.chat else "",
                            attachment,
                            attachment_type,
                            str(message.date),
                            message.media_group_id,
                            0
                        )
                    )
                    db.session.commit()

# app.run(get_messages("norppafi"))
app.run()
