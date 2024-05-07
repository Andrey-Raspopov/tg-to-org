from collections import defaultdict

from flask import Flask, Response
from flask import render_template
from flask_sqlalchemy import SQLAlchemy

from models.message import Message

app = Flask(__name__)


db = SQLAlchemy(model_class=Message)
db_name = "tg.db"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_name}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
db.init_app(app)
with app.app_context():
    db.create_all()


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
