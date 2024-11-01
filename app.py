from collections import defaultdict

from flask import Flask, Response
from flask import render_template
from flask_sqlalchemy import SQLAlchemy

from models.message import ExtMessage, Channel, Media

app = Flask(__name__)

db = SQLAlchemy()
db_name = "export.db"
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
        posts = defaultdict(list)
        authors = defaultdict(dict)
        channels = db.session.query(Channel)
        # TODO: maybe implement unread counter for channel?
        for channel in channels:
            items = db.session.query(ExtMessage).filter(ExtMessage.Message != "").filter(
                ExtMessage.ContextID == channel.ID).limit(5)
            authors[channel.ID] = {'title': channel.Title, 'description': channel.About}
            for item in items:
                posts[item.ContextID].append([item])
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
    items = db.session.query(ExtMessage).filter(ExtMessage.Message != "").order_by(ExtMessage.ContextID).all()
    posts = defaultdict(list)
    authors = defaultdict(list)
    unread = {}
    for item in items:
        posts[item.ContextID].append([item])
        authors[item.ContextID] = db.session.query(Channel).filter(Channel.ID == item.ContextID).all()[0].Title
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
            db.session.query(ExtMessage)
            .filter(ExtMessage.ContextID == channel)
            .filter(ExtMessage.Message != "")
            .order_by(ExtMessage.ContextID)
            .limit(10)
            .all()
        )
        posts = defaultdict(list)
        authors = defaultdict(dict)
        attachments = defaultdict(list)
        channel = db.session.query(Channel).filter(Channel.ID == channel).one()
        for item in items:
            if item.MediaID:
                attachment = db.session.query(Media).filter(Media.ID == item.MediaID).one()
                attachment = f"{attachment.Type}-{attachment.Name}.{attachment.ID}.jpg"
                attachments[item.ContextID].append([attachment])
            posts[item.ContextID].append([item])
            authors[item.ContextID] = {'title': channel.Title, 'description': channel.About}
        print(posts)
        return render_template("index.html", items=posts, authors=authors, attachment=attachments)
    except Exception as exception:
        error_text = "<p>The error:<br>" + str(exception) + "</p>"
        hed = "<h1>Something is broken.</h1>"
        return hed + error_text


@app.route("/mp3/<mp3_filename>")
def stream_mp3(mp3_filename):
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
def stream_mp4(mp4_filename):
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
    item = db.session.query(ExtMessage).filter(ExtMessage.id == post_id).all()[0]
    if item.attachment_type:
        post = [item, parse(item.attachment_name, item.attachment_type)]
    else:
        post = [item]
    author = item.ContextID

    return render_template("post.html", post=post, author=author)


@app.route("/api/post/<post_id>/read")
def toggle_read(post_id):
    """
    Toggle "read" field on the post
    :param post_id: id of the post to "read"
    :return:
    """
    item = db.session.query(ExtMessage).filter(ExtMessage.id == post_id).all()[0]
    item.read = 1
    db.session.commit()
    return index()


@app.template_filter("get_block")
def template_filter(block, file):
    """
    IDK what this does, need to fix documentation
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


# @app.route("/<channel>/get_all")
# def get_all(channel):
#     get_messages(channel)


if __name__ == "__main__":
    app.run(debug=True)
