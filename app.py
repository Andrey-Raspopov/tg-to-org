from collections import defaultdict

from flask import Flask, Response
from flask import render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

db_name = "tg.db"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_name
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True

db = SQLAlchemy(app)


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    message_text = db.Column(db.String)
    author_id = db.Column(db.Integer)
    author_name = db.Column(db.String)
    sender_id = db.Column(db.Integer)
    sender_name = db.Column(db.String)
    attachment_name = db.Column(db.String)
    attachment_type = db.Column(db.String)
    date = db.Column(db.String)
    media_group_id = db.Column(db.String)

    def __init__(self, _message_text, _author_id, _author_name, _sender_id, _sender_name, _attachment_name,
                 _attachment_type, _date, _media_group_id):
        self.message_text = _message_text
        self.author_id = _author_id
        self.author_name = _author_name
        self.sender_id = _sender_id
        self.sender_name = _sender_name
        self.attachment_name = _attachment_name
        self.attachment_type = _attachment_type
        self.date = _date
        self.media_group_id = _media_group_id


def parse(string1, string2):
    a = string1.split(';')
    b = string2.split(';')
    r = {}
    for i in range(len(a)):
        r[a[i]] = b[i]
    return r


@app.route("/")
def hello_world():
    try:
        items = Message.query.order_by(Message.author_id).all()
        posts = defaultdict(list)
        authors = defaultdict(list)
        for item in items:
            if item.attachment_type:
                posts[item.author_id].append([item, parse(item.attachment_name, item.attachment_type)])
            else:
                posts[item.author_id].append([item])
            authors[item.author_id] = item.author_name
        print(posts)
        return render_template("index.html", items=posts, authors=authors)
    except Exception as e:
        # e holds description of the error
        error_text = "<p>The error:<br>" + str(e) + "</p>"
        hed = "<h1>Something is broken.</h1>"
        return hed + error_text


@app.route("/mp3/<mp3_filename>")
def streammp3(mp3_filename):
    def generate(mp3_filename):
        with open(f"static/tg_data/{mp3_filename}", "rb") as fmp3:
            data = fmp3.read(1024)
            while data:
                yield data
                data = fmp3.read(1024)

    return Response(generate(mp3_filename), mimetype="audio/mpeg")


@app.route("/mp4/<mp4_filename>")
def streammp4(mp4_filename):
    def generate(mp4_filename):
        with open(f"static/tg_data/{mp4_filename}", "rb") as fmp4:
            data = fmp4.read(1024)
            while data:
                yield data
                data = fmp4.read(1024)

    return Response(generate(mp4_filename), mimetype="audio/mpeg")


if __name__ == "__main__":
    app.run(debug=True)
