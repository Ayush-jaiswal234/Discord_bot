from discord.ext import commands,tasks
import aiosqlite
import typing
from datetime import datetime,timedelta,timezone
import discord
from scripts import nation_data_converter
from bot import loot_calculator

class beige_alerts(commands.Cog):
	def __init__(self,bot,):
		self.bot = bot
		self.updater = bot.updater
		self.alert_instances = []

	@commands.hybrid_command(name='beigealerts',with_app_command=True,description='Alerts about the targets leaving beige')
	async def beigealerts(self,ctx:commands.Context,city_range:str,alliance_id='Default',loot=0):
		channel = ctx.channel
		if alliance_id == 'Default':
			async with aiosqlite.connect('pnw.db') as db:
				async with db.execute('select * from safe_aa') as cursor:
					safe_aa = await cursor.fetchall()
				safe_aa = tuple([x[0] for x in safe_aa])
			date=datetime.now(timezone.utc).replace(microsecond=0)
			date = date -timedelta(days=10)
			alliance_search =  f"and (alliance_id not in {safe_aa} or (alliance_id in {safe_aa} and (alliance_position=1 or date(last_active)<'{date}')))"	
		else:
			alliance_id = tuple(alliance_id.split(','))
			alliance_search = f"and alliance_id in {alliance_id}" if len(alliance_id)>1 else f"alliance_id = {alliance_id[0]}"

		city_range = city_range.split('-')
		city_text = f"and cities>{city_range[0]} and cities<{city_range[1]}"
		
		alert_obj = alerts(city_text,alliance_search,channel,self.bot)
		self.alert_instances.append([channel.id,alert_obj])
		alert_obj.set_new_alerts.start()
		self.updater.update_nation_data.change_interval(minutes=2.5)
		alert_obj.check_for_beigealerts.start()
		await ctx.send(f"Alerts have been registered for nations with cities {city_range[0]}-{city_range[1]}.")

	@commands.hybrid_command(name='stopalerts',with_app_command=True,description='Stops all alerts in the channel')
	async def stopalerts(self,ctx:commands.context):
		remove_alert = None
		for alerts in self.alert_instances:
			if alerts[0] == ctx.channel.id:
				alerts.set_new_alerts.stop()
				alerts.check_for_beigealerts.stop()
				remove_alert = alerts
		self.alert_instances.remove(remove_alert)
		if self.alert_instances==[]:
			self.updater.update_nation_data.change_interval(minutes=5)		

class alerts():
	def __init__(self,city_text,alliance_search,channel,bot):
		self.channel = channel
		self.city_text = city_text
		self.alliance_search = alliance_search
		self.bot = bot

	@tasks.loop(hours=2)
	async def set_new_alerts(self):
		async with aiosqlite.connect('pnw.db') as db:
			db.row_factory = lambda cursor,row: list(row)
			async with db.execute(f'select nation_id,beige_turns from all_nations_data where vmode=0 and defensive_wars<>3 and color=0 {self.city_text} {self.alliance_search}') as cursor:
				beige_nations = await cursor.fetchall()
			[nations.append(self.channel.id) for nations in beige_nations]
			await db.executemany("insert into beige_alerts values (?,?,?)",beige_nations)
			await db.commit()

	@tasks.loop(minutes=2.5) 
	async def check_for_beigealerts(self):
		now_time = datetime.now(timezone.utc).time()
		async with aiosqlite.connect("pnw.db") as db:
			if now_time.hour%2==1 and now_time.minute>=51 and (now_time.minute+now_time.second/60)<53.5:
				await db.execute(f"UPDATE beige_alerts SET beige_turns = beige_turns-1")
				await db.commit()
			async with db.execute("select beige_alerts.nation_id, all_nations_data.beige_turns, beige_alerts.beige_turns, beige_alerts.channel_id, all_nations_data.nation, all_nations_data.alliance, all_nations_data.alliance_id, all_nations_data.score, all_nations_data.cities, all_nations_data.last_active, all_nations_data.soldiers, all_nations_data.tanks, all_nations_data.aircraft, all_nations_data.ships from beige_alerts inner join all_nations_data on  all_nations_data.nation_id = beige_alerts.nation_id") as cursor:
				beige_data = await cursor.fetchall()	
			if beige_data !=[]:
				for data in beige_data:

					if data[1] ==0 or data[2]==0:
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
						if int(result[0])>10000000:
							await channel.send(embed=embed)
						
									
						await db.execute(f'delete from beige_alerts where nation_id={data[0]}')
		
			else:
				self.check_for_beigealerts.stop()			
			await db.commit()		
	

async def setup(bot):
    await bot.add_cog(beige_alerts(bot))
