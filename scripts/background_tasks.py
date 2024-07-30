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

class background_tasks:

	def __init__(self,bot) -> None:
		self.channel = bot.get_channel(715222394318356541)
		self.api_v3_link='https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab'
		self.whitlisted_api_link = 'https://api.politicsandwar.com/graphql?api_key=871c30add7e3a29c8f07'
		self.update_nation_data.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout,JSONDecodeError)
		self.update_loot_data.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout)
		self.update_trade_price.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout)
		self.audit_members.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout)
		self.update_trade_price.start()
		self.update_nation_data.start()
		self.update_loot_data.start()
		self.copy_db.start()
		self.audit_members.start()
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

	@tasks.loop(time=dt.time(hour=6,minute=15,tzinfo=dt.timezone.utc))
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

	@tasks.loop(hours=24,reconnect=True)
	async def audit_members(self):
		query="""{game_info{radiation{global,north_america,south_america,europe,africa,asia,australia,antarctica}}

				alliances(id:11189){
  					data{
					color
					nations{
						continent,last_active,color,id,alliance_position,soldiers,tanks,aircraft,ships,spies,num_cities,discord,discord_id,offensive_wars_count,defensive_wars_count
						food,uranium,coal,iron,bauxite,oil,lead
						cities{
							date,coal_power,oil_power,farm,aluminum_refinery,munitions_factory,oil_refinery,nuclear_power,steel_mill,coal_mine,oil_well,lead_mine,uranium_mine,iron_mine,bauxite_mine,infrastructure,land
						}  
						arms_stockpile,bauxite_works,emergency_gasoline_reserve,iron_works,mass_irrigation,uranium_enrichment_program
					}}
				}}"""
		async with httpx.AsyncClient() as client:
			fetchdata=await client.post(self.whitlisted_api_link,json={'query':query})
			fetchdata = fetchdata.json()["data"]
		radiation = fetchdata["game_info"]["radiation"]
		fetchdata = fetchdata["alliances"]["data"][0]	
		mmr = [0 * 3000 ,2 * 250,5 * 15, 0 * 5]	
		mmr_raiders = [5 * 3000 ,0 * 250,0 * 15, 0 * 5]	
		unit_name = ["soldiers","tanks","aircraft","ships"]
		for nation in fetchdata["nations"]:
			if nation["alliance_position"]!="APPLICANT":
				if nation["num_cities"]>10:
					alert_required,message= await self.alert_checker(nation,fetchdata["color"],radiation,mmr,unit_name)
				else:
					alert_required,message= await self.alert_checker(nation,fetchdata["color"],radiation,mmr_raiders,unit_name)	
				if alert_required:
					discord_id = await self.member_info(nation)
					await self.channel.send(f"{discord_id} {message}")

		logging.info("Task audit_members ran successfully")

	async def member_info(self,nation):
		discord_id = None
		if nation["discord_id"]!=None:
			discord_id = nation["discord_id"]
		else:
			async with aiosqlite.connect('pnw.db') as db:	
				async with db.execute(f'select discord_id from registered_nations where nation_id={nation["id"]}') as cursor:
					discord_id = await cursor.fetchone()
			if discord_id!=None:
				discord_id = discord_id[0]		
		if discord_id!=None:
			nation["discord_id"]=discord_id
			return f"<@{discord_id}> \n"
		else:
			return f'https://politicsandwar.com/nation/id={nation["id"]} is not registered to the bot\n'

	async def alert_checker(self,nation,aa_color,radiation,mmr,unit_name):
		alert_required = False
		alert_text = "```"
		
		if nation["color"]!=aa_color and nation["color"]!="biege":
			alert_required = True
			alert_text = f"Please change your color {aa_color}\n"
		
		inactive_days = time_converter(dt.datetime.strptime(nation["last_active"].split('+')[0],'%Y-%m-%dT%H:%M:%S')).split('d')[0]
		if int(inactive_days)>5:
			alert_required = True
			alert_text = f"{alert_text}Please login you have been inactive for {inactive_days} day(s).\n"
		mmr_nation = [x * nation["num_cities"] for x in mmr]
		
		for units in range(0,len(mmr)):
			if nation[unit_name[units]]<mmr_nation[units]:
				alert_required = True
				alert_text = f"{alert_text} You are missing {mmr_nation[units]-nation[unit_name[units]]} {unit_name[units]} to reach the mmr.\n"
		
		if nation["spies"]<60:
			alert_required = True
			alert_text= f"{alert_text} You are missing {60-nation['spies']} spies to reach the mmr.\n"

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

		rad_mod = (radiation["global"]+radiation[continent(nation["continent"])])/1000

		raws_rev ={"food":0,"uranium":0,"coal":0,"oil":0,"iron":0,"lead":0,"bauxite":0}
		
		for city in nation["cities"]:
			base_pop = city["infrastructure"]*100 #later add crime and disease
			city_age_mod = int(time_converter(dt.datetime.strptime(city["date"].split('+')[0],'%Y-%m-%d')).split('d')[0])
			if city_age_mod!=0:
				city_age_mod =1 + log(city_age_mod)/15
				
			raws_rev["food"] -= ((base_pop**2)/125000000) + ((base_pop*city_age_mod-base_pop)/850)
			raws_rev["food"] += max(0,city["farm"]*(1+(city["farm"]*2.63-2.63)/100)*food_mod*(1-rad_mod))

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
					alert_text = f"{alert_text}You only have {nation[rss]} {rss} remaining which will last for less than {int(-nation[rss]/revenue)+1} days.\n"
					alert_required = True								
		alert_text = f"{alert_text}```"
		return alert_required,alert_text