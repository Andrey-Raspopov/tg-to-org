from flask import Flask
from flask import render_template
import json

app = Flask(__name__)


def back():
    result = []
    with open('db.json_lines', 'r') as dbfile:
        data = json.loads(dbfile.read())
        for obj in data:
            try:
                print(obj['text'])
                result.append(obj['text'])
            except:
                try:
                    print(obj['caption'])
                    result.append(obj['caption'])
                except:
                    pass
    return result





# back()

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text

db_name = 'tg.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_name
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

db = SQLAlchemy(app)


if __name__ == '__main__':
    app.run(debug=True)


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    message_text = db.Column(db.String)

@app.route("/")
def hello_world():
    try:
        items=Message.query.all()
        print(items)
        return render_template("index.html", items=items)
    except Exception as e:
        # e holds description of the error
        error_text = "<p>The error:<br>" + str(e) + "</p>"
        hed = '<h1>Something is broken.</h1>'
        return hed + error_text