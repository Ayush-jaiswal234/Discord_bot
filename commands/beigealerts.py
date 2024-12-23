from discord.ext import commands,tasks
import aiosqlite
from datetime import datetime,timedelta,timezone
import discord
from scripts import nation_data_converter
from bot import loot_calculator,monitor_targets
from web_flask import beige_link
import pnwkit

class beige_alerts(commands.Cog):
	def __init__(self,bot,):
		self.bot = bot
		self.updater = bot.updater
		self.safe_aa = []
		self.check_for_beigealerts.start()

	class MonitorFlags(commands.FlagConverter,delimiter= " ",prefix='-'):
		all_nations: bool = False
		alliances: str = 'Default'
		loot: int = 0
		time: int = 0

	async def flags_parser(self,all_nations,alliances):
		
		if alliances== 'Default' and all_nations==0:	
			date=datetime.now(timezone.utc).replace(microsecond=0)
			date = date -timedelta(days=10)
			alliance_search =  f"and (alliance_id not in {self.safe_aa} or (alliance_id in {self.safe_aa} and (alliance_position=1 or date(last_active)<'{date}')))"	
		elif all_nations==1:
			alliance_search = ""
		else:
			alliance_id = tuple(alliances.split(','))
			alliance_search = f"and alliance_id in {alliance_id}" if len(alliance_id)>1 else f"and alliance_id = {alliance_id[0]}"

		return alliance_search

	@commands.hybrid_command(name='beigealerts',with_app_command=True,description='Alerts about the targets leaving beige')
	async def beigealerts(self,ctx:commands.Context,*,flags:MonitorFlags):
		async with aiosqlite.connect('pnw.db') as db:
			await db.execute(f"INSERT OR REPLACE INTO beige_alerts values {(ctx.author.id,int(flags.all_nations),str(flags.alliances),flags.loot,flags.time)}")
			await db.commit()
		
		alliance_search = await self.flags_parser(flags.all_nations,flags.alliances)
		self.updater.update_nation_data.change_interval(minutes=2.5)
		if not self.check_for_beigealerts.is_running():
			self.check_for_beigealerts.start()	
		endpoint = f"{ctx.author}"	
		unique_link = beige_link(endpoint, [alliance_search,flags.loot])
		
		await ctx.send(f"Alerts have been set. Use this link to plan when you need to be online:\n{unique_link}")

	@commands.hybrid_command(name='stopalerts',with_app_command=True,description='Stops all alerts in the channel')
	async def stopalerts(self,ctx:commands.context):

		async with aiosqlite.connect('pnw.db') as db:
			await db.execute(f'delete from beige_alerts where user_id ={ctx.author.id}')
			await db.commit()

		await ctx.send("Alerts have been removed for you.")					

	async def is_alert_needed(self, target,user):
		if not bool(user['all_nations']):
			if user['alliances'] != "Default" and target['alliance_id'] not in (user['alliances'].split(',')):
				return False
			elif target['alliance_id'] in self.safe_aa:
				return False
		
		if user['loot']>target['loot']:
			return False
		
		return True

	@tasks.loop(minutes=2.5)
	async def check_for_beigealerts(self):
		now_time = datetime.now(timezone.utc).time()
		if now_time.hour % 2 == 1 and now_time.minute >= 57 and (now_time.minute + now_time.second / 60) < 59.5:
			async with aiosqlite.connect("pnw.db") as db:
				db.row_factory = aiosqlite.Row
				async with db.execute('select * from safe_aa') as cursor:
					safe_aa = await cursor.fetchall()
				safe_aa = tuple([x[0] for x in safe_aa])
				self.safe_aa = safe_aa
				async with db.execute("""
					SELECT nation_id, nation, alliance, alliance_id, score,cities, last_active, soldiers, tanks, aircraft, ships
					FROM all_nations_data WHERE beige_turns = 1""") as cursor:
					beige_data = await cursor.fetchall()

				async with db.execute("""
					SELECT beige_alerts.user_id, beige_alerts.all_nations,beige_alerts.alliances,beige_alerts.loot,beige_alerts.alert_time,
							all_nations_data.score
							FROM beige_alerts
							INNER JOIN registered_nations ON beige_alerts.user_id = registered_nations.discord_id
							INNER JOIN all_nations_data ON registered_nations.nation_id = all_nations_data.nation_id;""") as cursor:
					user_info = await cursor.fetchall()
				
				for target in beige_data:
					loot = await loot_calculator(target['nation_id'])
					if loot:
						target['loot'] = loot[0]
					else:
						target['loot'] = 'No loot info found'	
				# Loop through each alert and evaluate its conditions
				dm_dict = {}
				if beige_data:
					for user in user_info:
						for target in beige_data:
							if target['score']>user['score']*0.75 and target['score']<user['score']*2.5:
								if await self.is_alert_needed(target,user):
									dm_dict.setdefault(user['user_id'], []).append(target)

				for user,targets in dm_dict:
					await self.send_alert(user,targets)

	async def send_alert(self,user,targets):
		dm_channel = self.bot.get_user(user) or  self.bot.fetch_user(user)
		
		emb_list = []
		for target in targets:
			embed = discord.Embed()
			embed.title = f"Target: {target['nation']}"
			if type(target['loot'])==int:
				embed.description = f"Total loot: ${target['loot']:,.2f}"
			else:
				embed.description = target['loot']

			embed.add_field(name="Nation info",
							value=f"Target: [{target['nation']}](https://politicsandwar.com/nation/war/declare/id={target['nation_id']})\n"
								f"Alliance: [{target['alliance']}](https://politicsandwar.com/alliance/id={target['alliance_id']})\n"
								"```js\n"
								f" Cities: {target['cities']} \n"
								f"Last Active: {nation_data_converter.time_converter(datetime.strptime(target['last_active'],'%Y-%m-%d %H:%M:%S'))}```",
								inline=False)
			embed.add_field(name="Military info",
							value=f"```js\n"
								f"Soldiers: {target['soldiers']:<8,}"
								f"Tanks: {target['tanks']:<8,}\n"
								f"Aircraft: {target['aircraft']:<8,}"
								f"Ships: {target['ships']:<8,}```",
								inline=False)	
			
			emb_list.append(embed)

		await dm_channel.send(f'These nations are coming out of beige next turn which is in ....',embeds=emb_list)	
				


async def setup(bot):
    await bot.add_cog(beige_alerts(bot))
