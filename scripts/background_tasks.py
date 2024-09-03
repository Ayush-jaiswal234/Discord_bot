import aiosqlite,httpx,time,logging
from discord.ext import tasks
from sqlite3 import OperationalError
from httpx import ReadTimeout,ConnectTimeout
import datetime as dt
from googleapiclient.http import MediaFileUpload 
from google.oauth2 import service_account
from googleapiclient.discovery import build
from scripts.nation_data_converter import time_converter
from json.decoder import JSONDecodeError
from math import log
from scripts.nation_data_converter import continent
from discord.errors import Forbidden
from apscheduler.schedulers.asyncio import AsyncIOScheduler

info_time = dt.time(hour=22,minute=0,tzinfo=dt.timezone.utc)

class background_tasks:

	def __init__(self,bot) -> None:
		self.bot = bot
		self.channel = bot.get_channel(1147384907694354452)
		self.scheduler = AsyncIOScheduler()
		self.scheduler.add_job(self.spies_checker, trigger='cron',day_of_week='fri', hour=12, minute=00,timezone=dt.timezone.utc)
		self.api_v3_link='https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab'
		self.whitlisted_api_link = 'https://api.politicsandwar.com/graphql?api_key=871c30add7e3a29c8f07'

		self.scheduler.start()
		self.update_nation_data.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout,JSONDecodeError)
		self.update_loot_data.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout)
		self.update_trade_price.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout)
		self.update_safe_aa.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout)
		self.audit_members.add_exception_type(OperationalError,KeyError,ConnectTimeout)
		self.update_trade_price.start()
		self.update_nation_data.start()	
		self.update_loot_data.start()
		self.copy_db.start()
		self.audit_members.start()
		self.update_safe_aa.start()
		pass

	@tasks.loop(minutes=5,reconnect=True)
	async def update_nation_data(self):
		start_time=time.time()
		request_url='https://politicsandwar.com/api/v2/nations/819fd85fdca0a686bfab/&min_score=20'
		async with httpx.AsyncClient() as client:
			nationdata= await client.get(request_url,timeout=20)
			nationdata=nationdata.json()
		list_of_values=[]
		for x in nationdata['data']:
			values =tuple(value if not isinstance(value,str) else f"{value}" for value in x.values())
			list_of_values.append(values)
		async with aiosqlite.connect('pnw.db',timeout=20.0) as db:
			await db.execute('delete from all_nations_data')
			await db.executemany(f'''INSERT INTO all_nations_data VALUES ({','.join(['?' for x in range(0,len(list_of_values[0]))])})''', list_of_values)   
			await db.commit()
		end_time=time.time()
		logging.info(f'Time nation={end_time-start_time}')
	pass

	@tasks.loop(minutes=2,reconnect=True)
	async def update_loot_data(self):
		async with aiosqlite.connect('pnw.db',timeout=20.0) as db:
			start_time=time.time()
			query="""{wars(active:false,first:1000,status:INACTIVE){
						data{
							id,end_date,winner_id,att_id,def_id,war_type
							attacker{
								alliance_position,war_policy,advanced_pirate_economy
							}  
							defender{
								alliance_position,war_policy,advanced_pirate_economy
							}
						}
						}	}"""
			async with httpx.AsyncClient() as client:
				fetchdata=await client.post(self.api_v3_link,json={'query':query})
				fetchdata=fetchdata.json()['data']['wars']['data']
				for war in fetchdata:
					if war['winner_id'] != '0':
						loser_id= war['def_id'] if war['winner_id']==war['att_id'] else war['att_id']
						date=war['end_date'].split('+')[0]
						date_obj=time.strptime(date,"%Y-%m-%dT%H:%M:%S")
						search =('select war_end_date from loot_data where nation_id=%s') %(loser_id)
						cursor = await db.execute(search)
						compare_date=await cursor.fetchone()
						compare_date=time.strptime(compare_date[0],"%Y-%m-%dT%H:%M:%S") if compare_date!= None else compare_date
						if compare_date==None or compare_date<date_obj:
							war_query=f"""{{
								warattacks(war_id:{war['id']}){{
								data{{
									money_looted,food_looted,coal_looted,oil_looted,uranium_looted,lead_looted,iron_looted,bauxite_looted,gasoline_looted,munitions_looted,steel_looted,aluminum_looted
									}}	
								}}
								}}"""
							loot_data = await client.post(self.api_v3_link,json={'query':war_query})
							if 'Too Many Requests' in str(loot_data):
								break
							
							war_type = war['war_type']
							if war['winner_id']==war['att_id']:
								if war['defender']!=None:
									loser_aa_position = war['defender']['alliance_position']
									loser_war_policy = war['defender']['war_policy']
								else:
									loser_aa_position = "NOALLIANCE"
									loser_war_policy = None
								if war['attacker']!=None:		
									winner_war_policy = war['attacker']['war_policy']
									winner_ape = war['attacker']['advanced_pirate_economy']
								else:
									winner_war_policy = None
									winner_ape = False	
								attrition_def_win = False
							else:
								if war['attacker']!=None:
									loser_aa_position = war['attacker']['alliance_position']
									loser_war_policy = war['attacker']['war_policy']
								else:
									loser_aa_position = "NOALLIANCE"
									loser_war_policy = None
								if war['defender']!=None:		
									winner_war_policy = war['defender']['war_policy']
									winner_ape = war['defender']['advanced_pirate_economy']
								else:
									winner_war_policy = None
									winner_ape = False		
								attrition_def_win = True 	

							policy_modifier = 1
							if winner_war_policy == "ATTRITION":
								policy_modifier -= 0.2
							elif winner_war_policy == "PIRATE":
								policy_modifier += 0.4

							if loser_war_policy == "TURTLE":
								policy_modifier +=0.2
							elif loser_war_policy == "MONEYBAGS":
								policy_modifier -= 0.4
							elif loser_war_policy == "GUARDIAN":
								policy_modifier += 0.2

							type_modifier = 1
							if war_type == "ORDINARY":
								type_modifier = 0.5
							elif war_type == "RAID":
								type_modifier = 1
							else:	
								if attrition_def_win:
									type_modifier = 0.5
								else:
									type_modifier = 0.25

							ape_modifier = 1.1 if winner_ape else 1

							loot_modifier = policy_modifier*type_modifier*ape_modifier*10			


							loot_data=loot_data.json()['data']['warattacks']['data']
							loot_data = loot_data[1] if loser_aa_position not in ["NOALLIANCE","APPLICANT"] else loot_data[0]

							for loot_type in loot_data:
								loot_data[loot_type] = int((loot_data[loot_type]*100/loot_modifier)-loot_data[loot_type])

							loot=','.join(str(x) for x in loot_data.values())
							loot_with_text=','.join([f"{key.split('_')[0]}={value}" if 'lead' not in key else f"`{key.split('_')[0]}`={value}" for key,value in loot_data.items() ])
							data_to_be_inserted=(f"insert into loot_data values({war['id']},{loser_id},{loot},'{date}') on conflict(nation_id) do update set war_id={war['id']},{loot_with_text},war_end_date='{date}'")
							await db.execute(data_to_be_inserted)
			await cursor.close()
			await db.commit()
		end_time=time.time()
		logging.info(f'Time loot={end_time-start_time}')
	pass		

	@tasks.loop(hours=2,reconnect=True)
	async def update_trade_price(self):
		start_time=time.time()
		query="""{
				tradeprices(first:1){data{
					food,coal,oil,uranium,lead,iron,bauxite,gasoline,munitions,steel,aluminum
				} }
				}"""
		async with httpx.AsyncClient() as client:
			fetchdata=await client.post(self.api_v3_link,json={'query':query})
			fetchdata=fetchdata.json()['data']['tradeprices']['data'][0]
			logging.info(fetchdata)
		insert_text=','.join([f"{price}" for price in fetchdata.values()])
		sql_insert_to_table=f"insert into trade_prices values ({insert_text})"
		logging.info(sql_insert_to_table)
		async with aiosqlite.connect('pnw.db',timeout=20.0) as db:
			await db.execute("delete from trade_prices")
			await db.execute(sql_insert_to_table)
			await db.commit()
		end_time=time.time()
		logging.info(f'Time trade={end_time-start_time}')
	pass

	@tasks.loop(time=dt.time(hour=6,minute=15,tzinfo=dt.timezone.utc),reconnect=True)
	async def copy_db(self):
		scopes=['https://www.googleapis.com/auth/drive']
		credentials = service_account.Credentials.from_service_account_file('service_account.json', scopes=scopes)
		drive_service = build('drive', 'v3', credentials=credentials)
		results = drive_service.files().list(pageSize=100, fields="files(id, name)").execute() 
		items = results.get('files', [])
		for files in items:
			if files['name']=='pnw.db':
				f = drive_service.files().delete(fileId=files['id']).execute()
			f = None 
		file_metadata = {"name": "pnw.db"}
		media = MediaFileUpload("pnw.db", mimetype="application/x-sqlite3")
		file = (
			drive_service.files()
			.create(body=file_metadata, media_body=media, fields="id")
			.execute()
		)
		logging.info(f'File ID: {file.get("id")}')		
		drive_service.close()

	@tasks.loop(time=info_time,reconnect=True)
	async def audit_members(self):
		logging.info('Task audit_members started')
		query="""{game_info{radiation{global,north_america,south_america,europe,africa,asia,australia,antarctica}}

				alliances(id:11189){
  					data{
					color
					nations{
						vacation_mode_turns,continent,last_active,color,id,alliance_position,soldiers,tanks,aircraft,ships,num_cities,discord_id,offensive_wars_count,defensive_wars_count
						food,uranium,coal,iron,bauxite,oil,lead
						cities{
							date,barracks,factory,hangar,drydock,coal_power,oil_power,farm,aluminum_refinery,munitions_factory,oil_refinery,nuclear_power,steel_mill,coal_mine,oil_well,lead_mine,uranium_mine,iron_mine,bauxite_mine,infrastructure,land
						}  
						central_intelligence_agency,arms_stockpile,bauxite_works,emergency_gasoline_reserve,iron_works,mass_irrigation,uranium_enrichment_program
					}}
				}}"""
		async with httpx.AsyncClient() as client:
			fetchdata=await client.post(self.whitlisted_api_link,json={'query':query},timeout=None)
			fetchdata = fetchdata.json()["data"]
		data_dict = {}
		data_dict["radiation"]=fetchdata["game_info"]["radiation"]
		fetchdata = fetchdata["alliances"]["data"][0]	
			
		data_dict["mmr"] = {"soldiers":0 * 3000 ,"tanks":2 * 250,"aircraft":5 * 15,"ships": 0 * 5}	
		data_dict["mmr_raiders"] = {"soldiers":5 * 3000 ,"tanks":0 * 250,"aircraft":0 * 15,"ships": 0 * 5}		
		data_dict["mmr_buildings"]={"barracks":0,"factory":2,"hangar":5,"drydock":0}
		data_dict["raiders_buildings"]={"barracks":5,"factory":0,"hangar":0,"drydock":0}
		data_dict["color"]=fetchdata["color"]
		
		#data_dict["war"]=war
		audit_text_dict = {}
		for nation in fetchdata["nations"]:
			if nation["alliance_position"]!="APPLICANT" and nation["vacation_mode_turns"]==0:
				alert_required,message = await self.alert_checker(nation,data_dict)	
				
				if alert_required:
					discord_id = await self.member_info(nation)
					if discord_id!=None:
						try:
							user = await self.bot.get_user(discord_id)
						except:
							logging.info('get_user failed')	
							user = await self.bot.fetch_user(discord_id)
						try:
							await user.send(message)
						except Forbidden:
							await self.channel.send(f"<@{discord_id}> Why did you block me??? Please enable dm for the people you share the server with(For gov ref: https://politicsandwar.com/nation/id={nation['id']}).\nAs for the rest of the message:\n{message}")
					else:
						logging.info(f'{nation["id"]} not registered')	

		logging.info("Task audit_members ran successfully")

	async def member_info(self,nation):
		async with aiosqlite.connect('pnw.db') as db:	
			async with db.execute(f'select discord_id from registered_nations where nation_id={nation["id"]}') as cursor:
				discord_id = await cursor.fetchone()
		if discord_id!=None:
			discord_id = discord_id[0]
		else:
			discord_id = nation["discord_id"]
		
		return discord_id
			

	async def alert_checker(self,nation,data_dict):
		alert_required = False
		alert_text = ""
		
		if nation["color"]!=data_dict["color"] and nation["color"]!="biege":
			alert_required = True
			alert_text = f"{alert_text}**Color:**\n```Please change your color {data_dict['color']}.```\n"
		
		inactive_days = time_converter(dt.datetime.strptime(nation["last_active"].split('+')[0],'%Y-%m-%dT%H:%M:%S')).split('d')[0]
		if int(inactive_days)>5:
			alert_required = True
			alert_text = f"{alert_text}**Inactivity:**\n```Please login you have been inactive for {inactive_days} day(s).```\n"
		
		if nation["num_cities"]>10:
			mmr_nation = {k:v* nation["num_cities"] for k,v in data_dict["mmr"].items()}
			mmr_buildings ={k:v* nation["num_cities"] for k,v in data_dict["mmr_buildings"].items()}
		else:
			mmr_nation = {k:v* nation["num_cities"] for k,v in data_dict["mmr_raiders"].items()}
			mmr_buildings ={k:v* nation["num_cities"] for k,v in data_dict["raiders_buildings"].items()}
		
		actual_mmr_buildings ={"barracks":0,"factory":0,"hangar":0,"drydock":0}
		for city in nation["cities"]:
			for keys in actual_mmr_buildings:
				actual_mmr_buildings[keys]+=city[keys]

		for keys in mmr_nation:
			if nation[keys]<mmr_nation[keys]:
				alert_required = True
				alert_text = f"{alert_text}**{keys.capitalize()}:**\n```You are missing {mmr_nation[keys]-nation[keys]} {keys} to reach the mmr.```\n"

		for keys in actual_mmr_buildings:
			if actual_mmr_buildings[keys]<mmr_buildings[keys]:
				alert_required = True
				alert_text = f"{alert_text}**{keys.capitalize()}:**\n```You are missing {mmr_buildings[keys]-actual_mmr_buildings[keys]} {keys} to reach mmr.```\n"


		muni_mod = 1
		if nation["arms_stockpile"]:
			muni_mod =1.34

		steel_mod = 1
		if nation["iron_works"]:
			steel_mod = 1.36

		alum_mod = 1
		if nation["bauxite_works"]:
			alum_mod = 1.36	

		gas_mod = 1
		if nation["emergency_gasoline_reserve"]:
			gas_mod = 2

		ura_mod = 1
		if nation["uranium_enrichment_program"]:
			ura_mod = 2 	

		food_mod = 1/500
		if nation["mass_irrigation"]:
			food_mod = 1/400
		if nation["continent"]=="an":
			food_mod = food_mod*0.5
		
		rad_mod = (data_dict["radiation"]["global"]+data_dict["radiation"][continent(nation["continent"])])/1000

		raws_rev ={"food":0,"uranium":0,"coal":0,"oil":0,"iron":0,"lead":0,"bauxite":0}
		
		for city in nation["cities"]:
			base_pop = city["infrastructure"]*100 #later add crime and disease
			city_age_mod = int(time_converter(dt.datetime.strptime(city["date"].split('+')[0],'%Y-%m-%d')).split('d')[0])
			if city_age_mod!=0:
				city_age_mod =1 + log(city_age_mod)/15
				
			raws_rev["food"] -= ((base_pop**2)/125000000) + ((base_pop*city_age_mod-base_pop)/850)
			raws_rev["food"] += city["farm"]*(1 + ((0.5 *(city["farm"] - 1)) / (20 - 1)))*food_mod*city["land"]*(1-rad_mod)*12

			unpowered_infra = city["infrastructure"]
			raws_rev["uranium"] += 3*city["uranium_mine"]*(1+(city["uranium_mine"]*12.5-12.5)/100)*ura_mod
			for plant in range(0,city['nuclear_power']):
				raws_rev["uranium"] -= 2.4
				unpowered_infra -= 1000
				if unpowered_infra>0:
					raws_rev["uranium"] -=2.4
					unpowered_infra -=1000

			raws_rev["coal"] += 3*city["coal_mine"]*(1+(city["coal_mine"]*5.555-5.55)/100)
			raws_rev["coal"] -= 3*city["steel_mill"]*(1+(city["steel_mill"]*12.5-12.5)/100)*steel_mod	
			for plant in range(0,city['coal_power']):
				i=0
				while unpowered_infra>0 and i<5:
					raws_rev["coal"] -= 1.2
					unpowered_infra -=100

			raws_rev["oil"] += 3*city["oil_well"]*(1+(city["oil_well"]*5.555-5.55)/100)	
			raws_rev["oil"] -= 3*city["oil_refinery"]*(1+(city["oil_refinery"]*12.5-12.5)/100)*gas_mod
			for plant in range(0,city["oil_power"]):
				i=0
				while unpowered_infra>0 and i<5:
					raws_rev["oil"] -= 1.2
					unpowered_infra -=100

			raws_rev["iron"] += 3*city["iron_mine"]*(1+(city["iron_mine"]*5.555-5.55)/100)
			raws_rev["iron"] -= 3*city["steel_mill"]*(1+(city["steel_mill"]*12.5-12.5)/100)*steel_mod	

			raws_rev["lead"] += 3*city["lead_mine"]*(1+(city["lead_mine"]*5.555-5.55)/100)
			raws_rev["lead"] -= 6*city["munitions_factory"]*(1+(city["munitions_factory"]*12.5-12.5)/100)*muni_mod

			raws_rev["bauxite"] += 3*city["bauxite_mine"]*(1+(city["bauxite_mine"]*5.555-5.55)/100)	
			raws_rev["bauxite"] -= 3*city["aluminum_refinery"]*(1+(city["aluminum_refinery"]*12.5-12.5)/100)*alum_mod

		if nation["offensive_wars_count"]+nation["defensive_wars_count"]>0:
			raws_rev["food"] -= nation["soldiers"]/750
		else:
			raws_rev["food"] -= nation["soldiers"]/500			 
		
		for rss,revenue in raws_rev.items():
			if revenue<0:
				if nation[rss]<-revenue*3: 
					alert_text = f"{alert_text}**{rss.capitalize()}:**\n```You only have {nation[rss]} {rss} remaining which will last for {round(abs(nation[rss]/revenue),2)} days.```\n"
					alert_required = True								
		
		return alert_required,alert_text
	
	async def spies_checker(self):
		query="""{
				alliances(id:11189){
  					data{
					nations{
						spies,discord_id,nation_name,id,central_intelligence_agency,vacation_mode_turns,alliance_position
					} }
				} }"""
		async with httpx.AsyncClient() as client:
			fetchdata=await client.post(self.whitlisted_api_link,json={'query':query},timeout=None)
			fetchdata = fetchdata.json()["data"]['alliances']['data'][0]['nations']

		alert_text=""
		for nation in fetchdata:
			if nation["alliance_position"]!="APPLICANT" and nation["vacation_mode_turns"]==0:
				max_spies = 50
				if nation["central_intelligence_agency"]:
					max_spies = 60

				if nation["spies"]<max_spies:
					discord_id = await self.member_info(nation)
					if discord_id!=None:
						discord_id = f"<@{discord_id}>"
					else:
						discord_id = f"[{nation['nation_name']}](<https://politicsandwar.com/nation/id={nation['id']}>)"
					alert_text=f"{alert_text}{discord_id} "

		if alert_text!="":
			await self.channel.send(f"Weekly Reminder to Buy Spies!!!\n{alert_text}")

	@tasks.loop(hours=4,reconnect=True)
	async def update_safe_aa(self):
		query ="""{alliances(first:25,orderBy:{order:DESC,column:SCORE}){
					data{id}
					}
					treaties(first:1000){
						data{alliance1_id,alliance2_id,treaty_type}
					}
					}"""
		async with httpx.AsyncClient() as client:
			fetchdata= await client.post(self.api_v3_link,json={'query':query})
			fetchdata = fetchdata.json()["data"]	
		top_aa = {x["id"] for x in fetchdata["alliances"]["data"]}
		safe_aa = top_aa.copy()
		treaties = fetchdata["treaties"]["data"]	
		for treaty in treaties:
			if (treaty["alliance1_id"] in top_aa and treaty["treaty_type"] in ['Protectorate','MDP','Extension','MDoAP']) or (treaty["alliance1_id"] in safe_aa and treaty["treaty_type"] in ['Extension']):
				safe_aa.add(treaty["alliance2_id"])
			elif (treaty["alliance2_id"] in top_aa and treaty["treaty_type"] in ['Protectorate','MDP','Extension','MDoAP']) or (treaty["alliance2_id"] in safe_aa and treaty["treaty_type"] in ['Extension']):
				safe_aa.add(treaty["alliance1_id"])

		async with aiosqlite.connect('pnw.db') as db:
			await db.execute('DELETE FROM safe_aa')
			await db.executemany('INSERT INTO safe_aa (alliance_id) VALUES (?)', [(alliance_id,) for alliance_id in safe_aa])
			await db.commit()
		pass			
