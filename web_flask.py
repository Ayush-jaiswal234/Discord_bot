from flask import Flask,render_template,request,jsonify
from threading import Thread
import os
import jinja2
import datetime
from bot import targets,monitor_targets,aa_stalker,spy_target_finder

app = Flask('')


@app.route('/')
def main():
    return render_template('home.html')

@app.route('/commands')
def commands():
    return render_template('commands.html')

@app.route('/guides')
def guides():
    return render_template('guides.html')

@app.route('/stalker', methods=['GET', 'POST'])
async def stalker():
    if request.method == 'GET':
        return render_template('stalker.html')
    elif request.method == 'POST':
        if not request.is_json:
            return jsonify({"error": "Invalid Content-Type, expected application/json"}), 415

        # Parse the JSON payload
        data = request.get_json()
        alliance_ids = data.get('alliance_ids', '') 

        if not alliance_ids:
            return jsonify({"error": "No alliance IDs provided"}), 400

        fetchdata = await aa_stalker(alliance_ids)
        return jsonify(fetchdata)

@app.route('/spysheet', methods=['GET', 'POST'])
async def spysheet():
    if request.method == 'GET':
        return render_template('spysheet.html')
    elif request.method == 'POST':
        if not request.is_json:
            return jsonify({"error": "Invalid Content-Type, expected application/json"}), 415

        # Parse the JSON payload
        data = request.get_json()
        att_ids = data.get('attids', '') 
        def_ids = data.get('defids','')
        fetchdata = await spy_target_finder(att_ids,def_ids)
        return jsonify(fetchdata)

def run():
    Thread(target=lambda: app.run(host=os.getenv('web_address'), port=5000)).start()

env = jinja2.Environment(
        loader=jinja2.FileSystemLoader('templates'),
        autoescape=True
    )
env.filters['comma'] = lambda value: f"{value:,}"

# Temporary storage for user data (replace with preferred method)
user_data = {}  # Key: unique ID, Value: (parameters, expiration time)

def generate_link(user_id, parameters, expiration_time=30):  # Adjust expiration time
    unique_id = str(user_id)  # Generate unique identifier
    user_data[unique_id] = (parameters, datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=expiration_time))
    return f"http://{os.getenv('web_address')}:5000/raids/{unique_id}"

def beige_link(city_id,parameters,expiration_time=30):
    unique_id = str(city_id)
    user_data[unique_id] = (parameters, datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=expiration_time))
    return f"http://{os.getenv('web_address')}:5000/beige_monitor/{unique_id}"

@app.route('/raids/<unique_id>')
async def raid_view(unique_id):
    print('start')
    if unique_id not in user_data:
        return "Invalid link or data expired.", 404
    parameters, _ = user_data[unique_id]
    # Fetch data based on parameters
    list_of_targets = await targets(*parameters)
    #del user_data[unique_id]  # Remove data after use
    template = env.get_template('raid.html')
    result = template.render(targets=list_of_targets)
    return str(result)

@app.route('/war/<unique_id>')
async def war_view(unique_id):
    print('start')
    if unique_id not in user_data:
        return "Invalid link or data expired.", 404
    parameters, _ = user_data[unique_id]
    # Fetch data based on parameters
    list_of_targets = await targets(*parameters)
    #del user_data[unique_id]  # Remove data after use
    template = env.get_template('war.html')
    result = template.render(targets=list_of_targets)
    return str(result)

@app.route('/beige_monitor/<city_id>')
async def beige_view(city_id):
    print('start')
    if city_id not in user_data:
        return "Invalid link or data expired.", 404
    parameters, _ = user_data[city_id]
    # Fetch data based on parameters
    list_of_targets = await monitor_targets(*parameters,search_only=True)
    list_of_targets = [x for x in list_of_targets]
    #del user_data[unique_id]  # Remove data after use
    template = env.get_template('beige_monitor.html')
    result = template.render(targets=list_of_targets)
    return str(result)

if __name__=='__main__':
    app.run(debug=True)