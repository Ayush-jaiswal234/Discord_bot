from discord.ext import commands,tasks
import aiosqlite
from datetime import datetime,timedelta,timezone
import discord
from scripts import nation_data_converter
from bot import loot_calculator,monitor_targets
from web_flask import beige_link

class beige_alerts(commands.Cog):
	def __init__(self,bot,):
		self.bot = bot
		self.updater = bot.updater
		self.check_for_beigealerts.start()
		self.set_new_alerts.start()

	class MonitorFlags(commands.FlagConverter,delimiter= " ",prefix='-'):
		all_nations: bool = False
		alliances: str = 'Default'
		loot: int = 0

	async def flags_parser(self,city_range,all_nations,alliances):
		
		if alliances== 'Default' and all_nations==0:
			async with aiosqlite.connect('pnw.db') as db:
				async with db.execute('select * from safe_aa') as cursor:
					safe_aa = await cursor.fetchall()
			safe_aa = tuple([x[0] for x in safe_aa])	
			date=datetime.now(timezone.utc).replace(microsecond=0)
			date = date -timedelta(days=10)
			alliance_search =  f"and (alliance_id not in {safe_aa} or (alliance_id in {safe_aa} and (alliance_position=1 or date(last_active)<'{date}')))"	
		elif all_nations==1:
			alliance_search = ""
		else:
			alliance_id = tuple(alliances.split(','))
			alliance_search = f"and alliance_id in {alliance_id}" if len(alliance_id)>1 else f"alliance_id = {alliance_id[0]}"

		city_text = city_range.split('-')
		city_text = f"and cities>{city_text[0]} and cities<{city_text[1]}"	

		return city_text,alliance_search

	@commands.hybrid_command(name='beigealerts',with_app_command=True,description='Alerts about the targets leaving beige')
	async def beigealerts(self,ctx:commands.Context,city_range:str,*,flags:MonitorFlags):
		async with aiosqlite.connect('pnw.db') as db:
			await db.execute(f"INSERT INTO persistent_alerts values {(ctx.channel.id,city_range,int(flags.all_nations),flags.alliances,flags.loot)}")
			await db.commit()
		
		city_text,alliance_search = await self.flags_parser(city_range,flags.all_nations,flags.alliances)
		self.updater.update_nation_data.change_interval(minutes=2.5)
		if not self.set_new_alerts.is_running():
			self.set_new_alerts.start()
		if not self.check_for_beigealerts.is_running():
			self.check_for_beigealerts.start()	
		endpoint = f"{city_range}_{ctx.channel.id}"	
		unique_link = beige_link(endpoint, [city_text,alliance_search,flags.loot])
		
		await ctx.send(f"Alerts have been registered for nations with cities {city_range}.\nUse this link to plan when you need to be online:\n{unique_link}")

	@commands.hybrid_command(name='stopalerts',with_app_command=True,description='Stops all alerts in the channel')
	async def stopalerts(self,ctx:commands.context):

		async with aiosqlite.connect('pnw.db') as db:
			await db.execute(f'delete from persistent_alerts where channel_id ={ctx.channel.id}')
			await db.execute(f'delete from beige_alerts where channel_id ={ctx.channel.id} AND user_id IS NULL')
			await db.commit()
			async with db.execute('select * from persistent_alerts') as cursor:
				all_alerts = await cursor.fetchall()
		if all_alerts==None:
			self.updater.update_nation_data.change_interval(minutes=5)	
			self.set_new_alerts.stop()
		await ctx.send("All alerts for this channel have been stopped.")			
		

	@commands.hybrid_command(name='alertme',with_app_command=True,description='Pings the user before a nation is leaving beige.')
	async def alertme(self,ctx:commands.context,link):		
		if link.startswith('http'):
			nation_id=int(link[37:])
		else:
			nation_id=link
		async with aiosqlite.connect('pnw.db') as db:
			async with db.execute(f'select beige_turns from all_nations_data where nation_id={nation_id}') as cursor:
				beige_turns =  await cursor.fetchone()
			if beige_turns==None:
				await ctx.send("No such nation found")
			elif beige_turns[0]==0:
				await ctx.send("The nation is already out of beige")
			else:
				await db.execute(f'INSERT INTO beige_alerts values {tuple([nation_id,beige_turns[0],ctx.channel.id,ctx.author.id])}')		
				await db.commit()
				if not self.check_for_beigealerts.is_running():
					self.check_for_beigealerts.start()	
				await ctx.send(f"Alert for {link} has been set.")		

	def is_alert_needed(self, nation_data, city_range, alliance_condition, loot_condition):
    	# Check city range condition
		min_cities, max_cities = map(int, city_range.split('-'))
		if not (min_cities <= nation_data["cities"] <= max_cities):
			return False
		
		# Check alliance condition
		if alliance_condition != "Default" and nation_data["alliance_id"] not in alliance_condition:
			return False
		
		# Check loot condition (if any)
		if loot_condition > 0 and nation_data["loot"] < loot_condition:
			return False
		
		return True

	@tasks.loop(minutes=2.5)
	async def check_for_beigealerts(self):
		now_time = datetime.now(timezone.utc).time()
		async with aiosqlite.connect("pnw.db") as db:
			# Update beige turns periodically
			if now_time.hour % 2 == 1 and now_time.minute >= 51 and (now_time.minute + now_time.second / 60) < 53.5:
				await db.execute(f"UPDATE beige_alerts SET beige_turns = beige_turns - 1")
				await db.commit()
			
			# Fetch all the registered alerts
			async with db.execute("""
				SELECT beige_alerts.nation_id, all_nations_data.beige_turns, 
					beige_alerts.beige_turns, beige_alerts.channel_id, 
					all_nations_data.nation, all_nations_data.alliance, 
					all_nations_data.alliance_id, all_nations_data.score, 
					all_nations_data.cities, all_nations_data.last_active, 
					all_nations_data.soldiers, all_nations_data.tanks, 
					all_nations_data.aircraft, all_nations_data.ships, 
					persistent_alerts.city_range, persistent_alerts.alliances, persistent_alerts.loot
				FROM beige_alerts
				INNER JOIN all_nations_data ON all_nations_data.nation_id = beige_alerts.nation_id
				INNER JOIN persistent_alerts ON persistent_alerts.channel_id = beige_alerts.channel_id
			""") as cursor:
				beige_data = await cursor.fetchall()

			# Loop through each alert and evaluate its conditions
			if beige_data:
				for data in beige_data:
					if data[1] ==0 or data[2]==0:
						city_range = data[14]
						alliance_condition = data[15]
						loot_condition = data[16]
						# Check if the current nation matches the conditions set for this alert
						if self.is_alert_needed(data, city_range, alliance_condition, loot_condition):
							# Send the alert if conditions are met
							await self.send_alert(data)

						await db.execute(f'delete from beige_alerts where nation_id={data[0]}')
						await db.commit()
			else:
				self.check_for_beigealerts.stop()

	async def send_alert(self,data):
		channel = self.bot.get_channel(data[3])
		
		embed = discord.Embed()
		embed.title = f"Target: {data[4]}"
		result = await loot_calculator(data[0])
		if result!= None:
			embed.description = f"Total loot: ${result[0]:,.2f}"
		else:
			embed.description = "No loot info for this nation"
			result = [0]

		embed.add_field(name="Nation info",
						value=f"Target: [{data[4]}](https://politicsandwar.com/nation/war/declare/id={data[0]})\n"
							f"Alliance: [{data[5]}](https://politicsandwar.com/alliance/id={data[6]})\n"
							"```js\n"
							f"War Range: {data[7]*0.75:,.2f}-{data[7]*2.5:,.2f} " 
							f" Cities: {data[8]} \n"
							f"Last Active: {nation_data_converter.time_converter(datetime.strptime(data[9],'%Y-%m-%d %H:%M:%S'))}```",
							inline=False)
		embed.add_field(name="Military info",
						value=f"```js\n"
							f"Soldiers: {data[10]:<8,}"
							f"Tanks: {data[11]:<8,}\n"
							f"Aircraft: {data[12]:<8,}"
							f"Ships: {data[13]:<8,}```",
							inline=False)	
		if data[2]>0:
			embed.set_footer(text="This nation came out of beige prematurely.")
		await channel.send(embed=embed)			
			
	@tasks.loop(hours=2)
	async def set_new_alerts(self):
		async with aiosqlite.connect('pnw.db') as db:
			db.row_factory = aiosqlite.Row
			async with db.execute('select * from persistent_alerts') as cursor:
				all_alerts = await cursor.fetchall()
			if all_alerts	:
				for alert in all_alerts:
					city_text,alliance_search = await self.flags_parser(alert['city_range'],alert['all_nations'],alert['alliances'])
					if alert['loot']!=0:
						targets = await monitor_targets(city_text,alliance_search,alert['loot'])	
						beige_nations = [(x["nation_id"],x["beige_turns"],self.channel.id,None) for x in targets]
							
					else:
						async with db.execute(f'select nation_id,beige_turns from all_nations_data where vmode=0 and defensive_wars<>3 and color=0 {city_text} {alliance_search}') as cursor:
							beige_nations = await cursor.fetchall()
						[nations.extend(self.channel.id,None) for nations in beige_nations]
					await db.executemany("insert into beige_alerts values (?,?,?,?)",beige_nations)
					await db.commit()
	


async def setup(bot):
    await bot.add_cog(beige_alerts(bot))
