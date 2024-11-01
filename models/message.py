from sqlalchemy import Column, Integer, String, BLOB
from sqlalchemy.orm import declarative_base

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
    author_avatar = Column(String)

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
            _author_avatar
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
        self.author_avatar = _author_avatar


class ExtMessage(Base):
    __tablename__ = "Message"
    ID = Column(Integer, primary_key=True)
    ContextID = Column(Integer)
    Date = Column(Integer)
    FromID = Column(Integer)
    Message = Column(String)
    ReplyMessageID = Column(Integer)
    ForwardID = Column(Integer)
    PostAuthor = Column(String)
    ViewCount = Column(Integer)
    MediaID = Column(Integer)
    Formatting = Column(String)
    ServiceAction = Column(String)

    #    "FOREIGN KEY (ForwardID) REFERENCES Forward(ID),"
    #    "FOREIGN KEY (MediaID) REFERENCES Media(ID),"
    #    "PRIMARY KEY (ID, ContextID))
    def __init__(
            self,
            _id,
            _context_id,
            _date,
            _from_id,
            _message,
            _reply_message_id,
            _forward_id,
            _post_author,
            _view_count,
            _media_id,
            _formatting,
            _service_action,
    ):
        self.ID = _id
        self.ContextID = _context_id
        self.Date = _date
        self.FromID = _from_id
        self.Message = _message
        self.ReplyMessageID = _reply_message_id
        self.ForwardID = _forward_id
        self.PostAuthor = _post_author
        self.ViewCount = _view_count
        self.MediaID = _media_id
        self.Formatting = _formatting
        self.ServiceAction = _service_action


class Channel(Base):
    __tablename__ = "Channel"
    ID = Column(Integer, primary_key=True)
    DateUpdated = Column(Integer)
    About = Column(String)
    Title = Column(String)
    Username = Column(String)
    PictureID = Column(Integer)
    PinMessageID = Column(Integer)

    def __init__(
            self,
            _id, _date_updated, _about, _title, _username, _picture_id, _pin_message_id):
        self.ID = _id
        self.DateUpdated = _date_updated
        self.About = _about
        self.Title = _title
        self.Username = _username
        self.PictureID = _picture_id
        self.PinMessageID = _pin_message_id

class Media(Base):
    __tablename__ = "Media"
    ID = Column(Integer, primary_key=True)
    Name = Column(String)
    MimeType = Column(String)
    Size = Column(Integer)
    ThumbnailID = Column(Integer)
    Type = Column(String)
    LocalID = Column(Integer)
    Secret = Column(Integer)
    FileReference = Column(BLOB)
    AccessHash = Column(Integer)
    MediaID = Column(Integer)
    Extra = Column(String)

    def __init__(self, _id, _name, _mime_type, _size, _thumbnail_id, _type, _local_id, _secret, _file_reference, _access_hash, _media_id, _extra):
        self.ID = _id
        self.Name = _name
        self.MimeType = _mime_type
        self.Size = _size
        self.ThumbnailID = _thumbnail_id
        self.Type = _type
        self.LocalID = _local_id
        self.Secret = _secret
        self.FileReference = _file_reference
        self.AccessHash = _access_hash
        self.MediaID = _media_id
        self.Extra = _extra
    # "FOREIGN KEY (ThumbnailID) REFERENCES Media(ID))"