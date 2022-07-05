import sqlite3

def init(db_name="tg.db"):
    conn = sqlite3.connect(db_name)
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
        [attachment_type] TEXT)"""
    )
    conn.commit()