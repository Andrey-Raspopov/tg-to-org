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


@app.route("/")
def hello_world():
    return render_template("index.html", items=back())


back()
