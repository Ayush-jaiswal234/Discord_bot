from flask import Flask,render_template,request,jsonify
from threading import Thread
import os
import jinja2
import datetime
from bot import targets,monitor_targets,aa_stalker
from scripts.spy_assigner import spy_target_finder
import aiosqlite

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
        filters = {'include_vm':data.get('include_vm')}

        if not alliance_ids:
            return jsonify({"error": "No alliance IDs provided"}), 400
        fetchdata = await aa_stalker(alliance_ids, filters)
        return jsonify(fetchdata)



@app.route('/spysheet', methods=['GET', 'POST'])
async def spysheet():
    if request.method == 'GET':
        attids = request.args.get('attids', '')  # Default to empty string if not provided
        defids = request.args.get('defids', '')
        show_empty_rows = request.args.get('empty_rows', 'false').lower() == 'true' # Pass old_data to template
        auto_submit = request.args.get('auto_submit', 'false').lower() == 'true'
        if auto_submit:  # Prevent unnecessary double rendering
            fetchdata = await spy_target_finder(attids, defids)
            if not show_empty_rows:
                fetchdata = [data for data in fetchdata if data['top_attackers']]
            return render_template('spysheet.html', old_data=fetchdata)
        return render_template('spysheet.html', old_data=None)
    elif request.method == 'POST':
        if not request.is_json:
            return jsonify({"error": "Invalid Content-Type, expected application/json"}), 415

        # Parse the JSON payload
        data = request.get_json()
        att_ids = data.get('attids', '') 
        def_ids = data.get('defids','')
        show_empty_rows = data.get('empty_rows','')
        fetchdata = await spy_target_finder(att_ids,def_ids)
        if not show_empty_rows:
            fetchdata = [data for data in fetchdata if data['top_attackers']]
        return jsonify(fetchdata)
        
def run():
    Thread(target=lambda: app.run(host=os.getenv('web_address'), port=5000)).start()

env = jinja2.Environment(
        loader=jinja2.FileSystemLoader('templates'),
        autoescape=True
    )
env.filters['comma'] = lambda value: f"{value:,}" if isinstance(value, (int, float)) else value


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

@app.route('/beige_monitor/<discord_id>')
async def beige_view(discord_id):
	async with aiosqlite.connect('pnw.db') as db:
		db.row_factory = aiosqlite.Row
		async with db.execute(f"""
			SELECT  beige_alerts.all_nations,beige_alerts.alliances,beige_alerts.loot,beige_alerts.alert_time,
					all_nations_data.score
					FROM beige_alerts
					INNER JOIN registered_nations ON beige_alerts.user_id = registered_nations.discord_id
					INNER JOIN all_nations_data ON registered_nations.nation_id = all_nations_data.nation_id
					WHERE beige_alerts.user_id={discord_id}""") as cursor:
			parameters = await cursor.fetchone()    
	if parameters:
		if parameters['alliances']== 'Default' and parameters['all_nations']==0:	
			date=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
			date = date -datetime.timedelta(days=10)
			async with aiosqlite.connect('pnw.db') as db:
				async with db.execute('select * from safe_aa') as cursor:
					safe_aa = await cursor.fetchall()
			safe_aa = tuple([x[0] for x in safe_aa])
			alliance_search =  f"and (alliance_id not in {safe_aa} or (alliance_id in {safe_aa} and (alliance_position=1 or date(last_active)<'{date}')))"	
		elif parameters['all_nations']==1:
			alliance_search = ""
		else:
			alliance_id = tuple(parameters['alliances'].split(','))
			alliance_search = f"and alliance_id in {alliance_id}" if len(alliance_id)>1 else f"and alliance_id = {alliance_id[0]}"

		war_range = f"and score>{parameters['score']*0.75} and score<{parameters['score']*2.5}"
		list_of_targets = await monitor_targets(war_range,alliance_search,parameters['loot'],search_only=True)
		list_of_targets = [x for x in list_of_targets]
		template = env.get_template('beige_monitor.html')
		result = template.render(targets=list_of_targets)
		return str(result)
	else:
		return "Invalid link or data expired.", 404

if __name__=='__main__':
    app.run(debug=True)