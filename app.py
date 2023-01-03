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
    read = db.Column(db.Integer)

    def __init__(
            self,
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


def parse(string1, string2):
    """
    Zip two strings
    :param string1: some string w
    :param string2: some string
    :return:
    """
    if string1 is None:
        return {}
    a = string1.split(";")
    b = string2.split(";")
    return dict(zip(a, b))


@app.route("/")
def index():
    """
    Render main page
    :return:
    """
    try:
        items = (
            Message.query.filter(Message.read != 1).order_by(Message.author_id).all()
        )
        posts = defaultdict(list)
        authors = defaultdict(list)
        for item in items:
            if item.attachment_type:
                posts[item.author_id].append(
                    [item, parse(item.attachment_name, item.attachment_type)]
                )
            else:
                posts[item.author_id].append([item])
            authors[item.author_id] = item.author_name
        print(posts)
        return render_template("index.html", items=posts, authors=authors)
    except Exception as exception:
        # e holds description of the error
        error_text = "<p>The error:<br>" + str(exception) + "</p>"
        hed = "<h1>Something is broken.</h1>"
        return hed + error_text


@app.route("/channels")
def render_channels():
    """
    Render channels page
    :return:
    """
    items = Message.query.order_by(Message.author_id).all()
    posts = defaultdict(list)
    authors = defaultdict(list)
    unread = {}
    for item in items:
        if item.attachment_type:
            posts[item.author_id].append(
                [item, parse(item.attachment_name, item.attachment_type)]
            )
        else:
            posts[item.author_id].append([item])
        if item.read == 0:
            if item.author_id in unread:
                unread[item.author_id] += 1
            else:
                unread[item.author_id] = 1
        authors[item.author_id] = item.author_name
    return render_template("authors.html", items=posts, authors=authors, unread=unread)


@app.route("/channel/<channel>")
def render_channel(channel):
    """
    Render channel
    :param channel: channel id
    :return:
    """
    try:
        items = (
            Message.query.filter(Message.read != 1)
            .filter(Message.author_id == channel)
            .order_by(Message.author_id)
            .all()
        )
        posts = defaultdict(list)
        authors = defaultdict(list)
        for item in items:
            if item.attachment_type:
                posts[item.author_id].append(
                    [item, parse(item.attachment_name, item.attachment_type)]
                )
            else:
                posts[item.author_id].append([item])
            authors[item.author_id] = item.author_name
        return render_template("index.html", items=posts, authors=authors)
    except Exception as exception:
        error_text = "<p>The error:<br>" + str(exception) + "</p>"
        hed = "<h1>Something is broken.</h1>"
        return hed + error_text


@app.route("/mp3/<mp3_filename>")
def streammp3(mp3_filename):
    """
    Stream audio attachment
    :param mp3_filename: filename of audio attachment
    :return:
    """

    def generate(mp3_filename):
        with open(f"static/tg_data/{mp3_filename}", "rb") as fmp3:
            data = fmp3.read(1024)
            while data:
                yield data
                data = fmp3.read(1024)

    return Response(generate(mp3_filename), mimetype="audio/mpeg")


@app.route("/mp4/<mp4_filename>")
def streammp4(mp4_filename):
    """
    Stream video attachment.
    :param mp4_filename: video filename
    :return:
    """

    def generate(mp4_filename):
        with open(f"static/tg_data/{mp4_filename}", "rb") as fmp4:
            data = fmp4.read(1024)
            while data:
                yield data
                data = fmp4.read(1024)

    return Response(generate(mp4_filename), mimetype="audio/mpeg")


@app.route("/api/post/<post_id>")
def get_post(post_id):
    """
    Render post.
    :param post_id: id of the post
    :return:
    """
    item = Message.query.filter(Message.id == post_id).all()[0]
    if item.attachment_type:
        post = [item, parse(item.attachment_name, item.attachment_type)]
    else:
        post = [item]
    author = item.author_name

    return render_template("post.html", post=post, author=author)


@app.route("/api/post/<post_id>/read")
def toggle_read(post_id):
    """
    Toggle "read" field on the post
    :param post_id: id of the post to "read"
    :return:
    """
    item = Message.query.filter(Message.id == post_id).all()[0]
    item.read = 1
    db.session.commit()
    return index()


@app.template_filter("get_block")
def template_filter(block, file):
    """
    Idk what this does, need to fix documentation
    :param block:
    :param file:
    :return:
    """
    html = render_template(file)
    # Then use regex or something to parse
    # or even simple splits (better with named blocks), like...
    content = html.split(f"{{%% {block} %s %%}}")[-1]
    content = content.split("{%% endblock %%}")[0]
    return content


if __name__ == "__main__":
    app.run(debug=True)
