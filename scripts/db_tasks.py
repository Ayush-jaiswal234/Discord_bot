import aiosqlite,httpx,time,logging
from discord.ext import tasks
from sqlite3 import OperationalError
from httpx import ReadTimeout,ConnectTimeout,RemoteProtocolError
import datetime as dt
from googleapiclient.http import MediaFileUpload 
from google.oauth2 import service_account
from googleapiclient.discovery import build
from json.decoder import JSONDecodeError
from scripts.event_bus import bus

class db_tasks:

	def __init__(self,kit) -> None:
		self.api_v3_link='https://api.politicsandwar.com/graphql?api_key=2bfb8817f934b00c5eb6'
		self.whitlisted_api_link = 'https://api.politicsandwar.com/graphql?api_key=871c30add7e3a29c8f07'
		self.kit = kit
		self.bus = bus

		self.update_nation_data.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout,JSONDecodeError,RemoteProtocolError)
		self.update_loot_data.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout,RemoteProtocolError)
		self.update_trade_price.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout,RemoteProtocolError)
		self.update_safe_aa.add_exception_type(OperationalError,KeyError,ReadTimeout,ConnectTimeout)
		pass

	def run(self):	
		self.update_trade_price.start()
		self.update_nation_data.start()	
		self.update_loot_data.start()
		self.copy_db.start()
		self.update_safe_aa.start()

	@tasks.loop(minutes=5,reconnect=True)
	async def update_nation_data(self):
		request_url='https://politicsandwar.com/api/v2/nations/2bfb8817f934b00c5eb6/&min_score=20'
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
		await self.bus.emit('nation_data_updated')
	pass

	@tasks.loop(minutes=2,reconnect=True)
	async def update_loot_data(self):
		async with aiosqlite.connect('pnw.db',timeout=20.0) as db:
			query="""{wars(active:false,first:1000,status:INACTIVE){
						data{
							id,end_date,winner_id,att_id,def_id,war_type,att_alliance_position,def_alliance_position
							attacker{
										war_policy,advanced_pirate_economy}  
							defender{
               						war_policy,advanced_pirate_economy}
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
									loser_aa_position = war['def_alliance_position']
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
									loser_aa_position = war['att_alliance_position']
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
	pass		

	@tasks.loop(hours=2,reconnect=True)
	async def update_trade_price(self):
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


	async def bankrecs(self):

		exclude = ['id','receiver_id','sender_type','receiver_type','banker_id','note','tax_id']
		#await self.populate_bankrecs()
		subscription = await self.kit.subscribe("bankrec","create",{'sender_type':1,'receiver_type':2,'exclude':exclude},self.bank_update) #'metadata':'true'

	async def bank_update(self,data):
		data = data['__dict__']
		async with aiosqlite.connect('pnw.db',timeout=20.0) as db:
			data['nation_id'] = data.pop('sender_id')
			data['date'] = data['date'].strftime('%Y-%m-%dT%H:%M:%S')
			columns = ", ".join(data.keys())
			placeholders = ", ".join(["?"] * len(data))
			values = tuple(data.values())
			query = f"INSERT OR IGNORE INTO bankrecs ({columns}) VALUES ({placeholders})"
			await db.execute(query, values)
			await db.commit()

	async def populate_bankrecs(self):
		exclude = ['id','receiver_id','banker_id','note','tax_id']
		request_url=f'https://api.politicsandwar.com/subscriptions/v1/snapshot/bankrec?api_key=2bfb8817f934b00c5eb6&exclude={",".join(exclude)}'
		async with httpx.AsyncClient() as client:
			nationdata= await client.get(request_url,timeout=20)
			nationdata=nationdata.json()

		columns = ['date', 'money', 'coal', 'oil', 'uranium', 'iron','bauxite', 'lead', 'gasoline', 'munitions','steel', 'aluminum', 'food', 'sender_id']
				
		values_list = [tuple(data[c].split('+')[0] if c == 'date' else data[c] for c in columns) for data in nationdata if data['sender_type']==1 and data['receiver_type']==2 ]

		columns.append('nation_id') 
		columns.remove('sender_id')
		placeholders = ", ".join(["?"] * len(columns))
		query = f"INSERT OR IGNORE INTO bankrecs ({','.join(columns)}) VALUES ({placeholders})"
		
		async with aiosqlite.connect('pnw.db',timeout=30.0) as db:
			await db.execute('delete from bankrecs')		
			await db.executemany(query, values_list)
			await db.commit()