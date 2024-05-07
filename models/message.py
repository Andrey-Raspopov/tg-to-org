from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase, declarative_base

Base = declarative_base()

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer)
    message_text = Column(String)
    author_id = Column(Integer)
    author_name = Column(String)
    sender_id = Column(Integer)
    sender_name = Column(String)
    attachment_name = Column(String)
    attachment_type = Column(String)
    date = Column(String)
    media_group_id = Column(String)
    read = Column(Integer)

    def __init__(
            self,
            _message_id,
            _message_text,
            _author_id,
            _author_name,
            _sender_id,
            _sender_name,
            _attachment_name,
            _attachment_type,
            _date,
            _media_group_id,
            _read,
    ):
        self.message_id = _message_id
        self.message_text = _message_text
        self.author_id = _author_id
        self.author_name = _author_name
        self.sender_id = _sender_id
        self.sender_name = _sender_name
        self.attachment_name = _attachment_name
        self.attachment_type = _attachment_type
        self.date = _date
        self.media_group_id = _media_group_id
        self.read = _read
