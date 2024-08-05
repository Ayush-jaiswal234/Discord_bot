from flask import Flask
from threading import Thread
import os

app = Flask('')


@app.route('/')
def main():
    return "It lives!!"

def run():
    Thread(target=lambda: app.run(host=os.getenv('web_address'), port=5000)).start()
