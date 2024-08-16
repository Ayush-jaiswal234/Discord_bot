from discord.ext import commands
import httpx
from scripts.nation_data_converter import time_converter,continent
import datetime as dt
from math import log
import aiosqlite
from discord import AllowedMentions

class audit_commands(commands.Cog):
	def __init__(self,bot):
		self.bot = bot
		self.whitelisted_api = 'https://api.politicsandwar.com/graphql?api_key=871c30add7e3a29c8f07'
		
	@commands.command()
	async def audit_aa(self,ctx:commands.Context,ping=False,war=False,alliance_id=11189):	

		query=f"""{{game_info{{radiation{{global,north_america,south_america,europe,africa,asia,australia,antarctica}} }}

				alliances(id:{alliance_id}){{
  					data{{
					color
					nations{{
						nation_name,vacation_mode_turns,continent,last_active,color,id,alliance_position,soldiers,tanks,aircraft,ships,spies,num_cities,discord,discord_id,offensive_wars_count,defensive_wars_count
						food,uranium,coal,iron,bauxite,oil,lead
						cities{{
							date,barracks,factory,hangar,drydock,coal_power,oil_power,farm,aluminum_refinery,munitions_factory,oil_refinery,nuclear_power,steel_mill,coal_mine,oil_well,lead_mine,uranium_mine,iron_mine,bauxite_mine,infrastructure,land
						}}  
						central_intelligence_agency,arms_stockpile,bauxite_works,emergency_gasoline_reserve,iron_works,mass_irrigation,uranium_enrichment_program
						 wars(active:true,status:ACTIVE){{
          					id
							}}
					}} }}
				}} }}"""

		async with httpx.AsyncClient() as client:
			fetchdata=await client.post(self.whitelisted_api,json={'query':query},timeout=None)
			fetchdata = fetchdata.json()["data"]
		radiation = fetchdata["game_info"]["radiation"]
		fetchdata = fetchdata["alliances"]["data"][0]
		data_dict = {}	
		data_dict["mmr"] = {"soldiers":0 * 3000 ,"tanks":2 * 250,"aircraft":5 * 15,"ships": 0 * 5}	
		data_dict["mmr_raiders"] = {"soldiers":5 * 3000 ,"tanks":0 * 250,"aircraft":0 * 15,"ships": 0 * 5}		
		data_dict["mmr_buildings"]={"barracks":0,"factory":2,"hangar":5,"drydock":0}
		data_dict["raiders_buildings"]={"barracks":5,"factory":0,"hangar":0,"drydock":0}
		data_dict["color"]=fetchdata["color"]
		data_dict["war"]=war
		audit_text_dict = {}
		for nation in fetchdata["nations"]:
			if nation["alliance_position"]!="APPLICANT" and nation["vacation_mode_turns"]==0:
				discord_id = await self.member_info(nation)
				if discord_id==None:
					data_dict["discord_id"] = f"[{nation['nation_name']}](<https://politicsandwar.com/nation/id={nation['id']}>)"
				else:
					data_dict["discord_id"] = f"<@{discord_id}>"	
				
				audit_text_dict = await self.alert_checker(nation,data_dict,audit_text_dict)

				revenue = await self.revenue_calc(radiation,nation)	
				for rss,revenue in revenue.items():
					if revenue<0:
						if nation[rss]<-revenue*3: 
							audit_text_dict[rss] = f"{audit_text_dict.get(rss,'')}{data_dict['discord_id']} {round(abs(nation[rss]/revenue),2)} days "

		final_message =""
		for key,text in audit_text_dict.items():
			if len(final_message)+len(text)+len(key)<1990:
				final_message =f"{final_message}**{key.capitalize()}**\n{text}\n\n"
			else:
				await ctx.send(final_message,allowed_mentions=AllowedMentions(users=ping))
				final_message = f"**{key.capitalize()}**\n{text}\n\n"		
		
		await ctx.send(final_message,allowed_mentions=AllowedMentions(users=ping))


	async def member_info(self,nation):
		async with aiosqlite.connect('pnw.db') as db:	
			async with db.execute(f'select discord_id from registered_nations where nation_id={nation["id"]}') as cursor:
				discord_id = await cursor.fetchone()
		if discord_id!=None:
			discord_id = discord_id[0]
			nation["discord_id"] = discord_id
		else:
			discord_id = nation["discord_id"]
		
		return discord_id

	async def alert_checker(self,nation,data_dict,audit_dict):

		if nation["color"]!=data_dict["color"] and nation["color"]!="biege":
			audit_dict["color"] = f"{audit_dict.get('color','')}{data_dict['discord_id']} "
		
		inactive_days = time_converter(dt.datetime.strptime(nation["last_active"].split('+')[0],'%Y-%m-%dT%H:%M:%S')).split('d')[0]
		if int(inactive_days)>5:
			audit_dict["inactive"] = f"{audit_dict.get('inactive','')}{data_dict['discord_id']} {int(inactive_days)} days "

		if not data_dict["war"]:
			if nation["num_cities"]>10:
				mmr_nation = {k:v* nation["num_cities"] for k,v in data_dict["mmr"].items()}
				mmr_buildings ={k:v* nation["num_cities"] for k,v in data_dict["mmr_buildings"].items()}
			else:
				mmr_nation = {k:v* nation["num_cities"] for k,v in data_dict["mmr_raiders"].items()}
				mmr_buildings ={k:v* nation["num_cities"] for k,v in data_dict["raiders_buildings"].items()}
				
				if len(nation["wars"])<5:
					audit_dict["raids"] = f"{audit_dict.get('raids','')}{data_dict['discord_id']} {len(nation['wars'])}/5 "
			
			actual_mmr_buildings ={"barracks":0,"factory":0,"hangar":0,"drydock":0}
			for city in nation["cities"]:
				for keys in actual_mmr_buildings:
					actual_mmr_buildings[keys]+=city[keys]
			
			for keys in mmr_nation:
				if nation[keys]<mmr_nation[keys]:
					audit_dict[keys] = f"{audit_dict.get(keys,'')}{data_dict['discord_id']} {nation[keys]:,}/{mmr_nation[keys]:,} "

			for keys in actual_mmr_buildings:
				if actual_mmr_buildings[keys]<mmr_buildings[keys]:
					audit_dict[keys] = f"{audit_dict.get(keys,'')}{data_dict['discord_id']} {actual_mmr_buildings[keys]:,}/{mmr_buildings[keys]:,} "

			max_spies =50
			if nation["central_intelligence_agency"]:
				max_spies = 60
			if nation["spies"]<max_spies:
				audit_dict["spies"] = f"{audit_dict.get('spies','')}{data_dict['discord_id']} {nation['spies']}/{max_spies} "		



		return audit_dict	

	async def revenue_calc(self,radiation,nation):	
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
		
		return raws_rev 			


async def setup(bot):
    await bot.add_cog(audit_commands(bot))