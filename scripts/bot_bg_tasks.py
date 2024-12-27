from math import log
from scripts.nation_data_converter import continent
from scripts.nation_data_converter import time_converter
from discord.errors import Forbidden
import datetime as dt
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlite3 import OperationalError
from httpx import ConnectTimeout
from discord.ext import tasks
import logging,httpx,aiosqlite,random
from scripts.spy_assigner import spy_target_finder

info_time = dt.time(hour=22,minute=0,tzinfo=dt.timezone.utc) 

class Bot_bg_Tasks:

	def __init__(self,bot) -> None:
		self.bot = bot
		self.channel = bot.get_channel(1147384907694354452)
		self.scheduler = AsyncIOScheduler()
		#self.scheduler.add_job(self.spies_checker, trigger='cron',day_of_week='fri', hour=12, minute=00,timezone=dt.timezone.utc)
		self.scheduler.add_job(self.send_spy_alerts, trigger='cron', hour=2, minute=0,timezone=dt.timezone.utc)
		self.api_v3_link='https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab'
		self.whitlisted_api_link = 'https://api.politicsandwar.com/graphql?api_key=871c30add7e3a29c8f07'

		self.audit_members.add_exception_type(OperationalError,ConnectTimeout)
		self.audit_members.start()
		self.scheduler.start()
		pass

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
		data_dict["mmr_raiders"] = {"soldiers":5 * 3000*0.8 ,"tanks":0 * 250,"aircraft":0 * 15,"ships": 0 * 5}		
		data_dict["mmr_buildings"]={"barracks":0,"factory":2,"hangar":5,"drydock":0}
		data_dict["raiders_buildings"]={"barracks":5,"factory":0,"hangar":0,"drydock":0}
		data_dict["color"]=fetchdata["color"]
		block_messages = ["You shouldn't have blocked me you silly baka!!💢","Why did you block me you absolute fucking retard?!?!\nYou unblock me RIGHT MEOW you fucking idiot or else I'm coming to your house!","Let me in your DMs, or Shinji will shit in your mailbox."]
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
							await self.channel.send(f"<@{discord_id}> {random.choice(block_messages)}\nP.S.{message}")
					else:
						logging.info(f'{nation["id"]} not registered')	

		logging.info("Task audit_members ran successfully")

	async def member_info(self,nation):
		async with aiosqlite.connect('pnw.db') as db:	
			async with db.execute(f'select discord_id from registered_nations where nation_id={nation["id"]}') as cursor:
				discord_id = await cursor.fetchone()
		if discord_id!=None:
			discord_id = discord_id[0]
		
		return discord_id
			

	async def alert_checker(self,nation,data_dict):
		alert_required = False
		alert_text = ""
		war = True
		if nation["color"]!=data_dict["color"] and nation["color"]!="beige":
			alert_required = True
			alert_text = f"{alert_text}**Color:**\n```Please change your color {data_dict['color']}.```\n"
		
		inactive_days = time_converter(dt.datetime.strptime(nation["last_active"].split('+')[0],'%Y-%m-%dT%H:%M:%S')).split('d')[0]
		if int(inactive_days)>3:
			alert_required = True
			alert_text = f"{alert_text}**Inactivity:**\n```Please login you have been inactive for {inactive_days} day(s).```\n"
		
		if not war:
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

	async def send_spy_alerts(self):
		att_ids = '11189'
		def_ids = '790,5012,12500,10523,9432,10334,4567,12453,12544,13268,619,13344,11339'
		fetchdata = await spy_target_finder(att_ids,def_ids)
		fetchdata = [data for data in fetchdata if data['top_attackers']]
		alerts = {}
		for spy_info in fetchdata:
			for attackers in spy_info['top_attackers']:
				if attackers['optimal_attack']['type']=='spy':
					kill_type = 'Assassinate spies'  
				elif attackers['optimal_attack']['type']=='nukes':
					kill_type = 'Sabotage Nukes'
				else:
					kill_type = 'Sabotage Missiles'	
				alerts[attackers['attacker']['id']] = f"{alerts.get(attackers['attacker']['id'],'')}- [{spy_info['defender']['nation_name']}](<https://politicsandwar.com/nation/espionage/eid={spy_info['defender']['id']}>) --> **{kill_type}** on **{attackers['optimal_attack']['level'].capitalize()}** using **{attackers['attacker']['spies']}** spies\n"
		for nation,message in alerts.items():
			x = {'id':nation}
			discord_id = await self.member_info(x)
			if discord_id!=None:
				message = f"Spy targets for today:\n{message}\nIf these targets are already spy slotted use this link:\n http://162.19.228.4:5000/spysheet?attids={att_ids}&defids={def_ids}&auto_submit=true \nand filter using your nation name to get the best possible target for you"
				try:
					user = await self.bot.get_user(discord_id)
				except:
					user = await self.bot.fetch_user(discord_id)
				try:
					await user.send(message)
				except Forbidden:
					await self.channel.send(f"<@{discord_id}>{message}")
			else:
				await self.channel.send(f"{x['id']} is not registered. They were assigned the targets:{message}")	