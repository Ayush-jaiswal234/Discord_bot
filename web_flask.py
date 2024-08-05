from flask import Flask,request,jsonify
from threading import Thread
import os

app = Flask('')


@app.route('/')
def main():
    return "It lives!!"

def run():
    Thread(target=lambda: app.run(host=os.getenv('web_address'), port=5000)).start()

endpoint_data = {}
@app.route('/raids', methods=['POST'])
def raids():
    data = request.json
    unique_endpoint = str(data['endpoint'])  # Generate a unique endpoint
    endpoint_data[unique_endpoint] = data
    return jsonify({"endpoint": unique_endpoint}), 200
