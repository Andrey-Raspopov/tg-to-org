from collections import defaultdict

from flask import Flask, Response
from flask import render_template, url_for
import json

app = Flask(__name__)


from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text

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


@app.route("/")
def hello_world():
    try:
        items = Message.query.order_by(Message.author_id).all()
        posts = defaultdict(list)
        authors = defaultdict(list)
        for item in items:
            authors[item.author_id] = item.author_name
            posts[item.author_id].append(item)
        return render_template("index.html", items=posts, authors=authors)
    except Exception as e:
        # e holds description of the error
        error_text = "<p>The error:<br>" + str(e) + "</p>"
        hed = "<h1>Something is broken.</h1>"
        return hed + error_text


@app.route("/mp3/<mp3_filename>")
def streammp3(mp3_filename):
    def generate(mp3_filename):
        with open(f"static/{mp3_filename}", "rb") as fmp3:
            data = fmp3.read(1024)
            while data:
                yield data
                data = fmp3.read(1024)

    return Response(generate(mp3_filename), mimetype="audio/mpeg")


@app.route("/mp4/<mp4_filename>")
def streammp4(mp4_filename):
    def generate(mp4_filename):
        with open(f"static/{mp4_filename}", "rb") as fmp4:
            data = fmp4.read(1024)
            while data:
                yield data
                data = fmp4.read(1024)

    return Response(generate(mp4_filename), mimetype="audio/mpeg")


if __name__ == "__main__":
    app.run(debug=True)
