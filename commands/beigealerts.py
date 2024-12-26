from discord.ext import commands,tasks
import aiosqlite
from datetime import datetime,timedelta,timezone
import discord
from scripts import nation_data_converter
from bot import loot_calculator,last_bank_rec
from web_flask import beige_link
import pnwkit,logging,httpx

class beige_alerts(commands.Cog):
	def __init__(self,bot,):
		self.bot = bot
		self.updater = bot.updater
		self.safe_aa = []
		self.kit = pnwkit.QueryKit("2b2db3a2636488")
		self.check_for_beigealerts.add_exception_type(KeyError)
		self.check_for_beigealerts.start()

	class MonitorFlags(commands.FlagConverter,delimiter= " ",prefix='-'):
		all_nations: bool = False
		alliances: str = 'Default'
		loot: int = 0
		time: int = 0

	@commands.Cog.listener()
	async def on_ready(self):
		# Start the watcher after the bot is ready
		logging.info("Beige watcher started.")
		#await self.beige_watcher()
		

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
		endpoint = f"{ctx.author.id}"	
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
			if user['alliances'] != "Default":  
				if str(target['alliance_id']) not in (user['alliances'].split(',')):
					return False
			else:
				if target['alliance_id'] in self.safe_aa:
					return False
		
		if user['loot']>target['loot']:
			return False
		
		return True

	@tasks.loop(minutes=2.5,reconnect=True)
	async def check_for_beigealerts(self):
		now_time = datetime.now(timezone.utc).time()
		if now_time.hour % 2 == 1 and now_time.minute >= 50 and (now_time.minute + now_time.second / 60) <= 52.5:
			async with aiosqlite.connect("pnw.db") as db:
				db.row_factory = aiosqlite.Row
				async with db.execute('select * from safe_aa') as cursor:
					safe_aa = await cursor.fetchall()
				safe_aa = tuple([x[0] for x in safe_aa])
				self.safe_aa = safe_aa
				async with db.execute("""
					SELECT all_nations_data.nation_id, all_nations_data.nation, all_nations_data.alliance, all_nations_data.alliance_id, all_nations_data.score,all_nations_data.cities, all_nations_data.soldiers, all_nations_data.tanks, all_nations_data.aircraft, all_nations_data.ships, loot_data.war_end_date
					FROM all_nations_data
					INNER JOIN loot_data on all_nations_data.nation_id = loot_data.nation_id
					WHERE beige_turns = 1 and defensive_wars<>3 and vmode=0""") as cursor:
					beige_data = await cursor.fetchall()
					beige_data.sort(key=lambda x:x['nation_id'])
				async with db.execute("""
					SELECT beige_alerts.user_id, beige_alerts.all_nations,beige_alerts.alliances,beige_alerts.loot,beige_alerts.alert_time,
							all_nations_data.score
							FROM beige_alerts
							INNER JOIN registered_nations ON beige_alerts.user_id = registered_nations.discord_id
							INNER JOIN all_nations_data ON registered_nations.nation_id = all_nations_data.nation_id;""") as cursor:
					user_info = await cursor.fetchall()
			bank_data = await last_bank_rec(beige_data)
			updated_targets = []
			query = f"""{{nations(id:{[x['nation_id'] for x in beige_data]},first:500){{
			data{{
				cities{{infrastructure}}
				}}
			}} }}"""
			async with httpx.AsyncClient() as client:
				fetchdata = await client.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':query})
				fetchdata = fetchdata.json()['data']['nations']['data']
			
			for i in range(len(beige_data)):
				target = dict(beige_data[i])
				loot = await loot_calculator(target['nation_id'])
				if loot:
					target['loot'] = int(loot[0])
				else:
					target['loot'] = 'No loot info found'	
				if bank_data[i] not in ['N/A','']:
					target['last_deposit'] = nation_data_converter.time_converter(datetime.strptime(bank_data[i],'%Y-%m-%dT%H:%M:%S'))
				else:	
					target['last_deposit'] = bank_data[i]		
				
				target['avg_infra'] = round(sum([x['infrastructure'] for x in fetchdata[i]['cities']])/target['cities'],2) 
				updated_targets.append(target)		
			# Loop through each alert and evaluate its conditions
			dm_dict = {}
			if beige_data:
				for user in user_info:
					for target in updated_targets:
						if target['score']>user['score']*0.75 and target['score']<user['score']*2.5:
							if await self.is_alert_needed(target,user):
								dm_dict.setdefault(user['user_id'], []).append(target)

			for user,targets in dm_dict.items():
				await self.send_alert(user,targets)

	async def send_alert(self,user,targets):
		try:
			dm_channel = await self.bot.get_user(user) 
		except:
			dm_channel = await self.bot.fetch_user(user)
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
								f"Cities: {target['cities']} \n"
								f"Average Infra: {target['avg_infra']}\n"
								f"Last Deposit: {target['last_deposit']}\n"
								f"Last War Loss: {nation_data_converter.time_converter(datetime.strptime(target['war_end_date'],'%Y-%m-%dT%H:%M:%S'))}```",
								inline=False)
			embed.add_field(name="Military info",
							value=f"```js\n"
								f"Soldiers: {target['soldiers']:<8,}"
								f"Tanks: {target['tanks']:<8,}\n"
								f"Aircraft: {target['aircraft']:<8,}"
								f"Ships: {target['ships']:<8,}```",
								inline=False)	
			
			emb_list.append(embed)
		now = datetime.now(timezone.utc)
		next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
		time_difference = int((next_hour - now).total_seconds())
		await dm_channel.send(f'These nations are coming out of beige next turn which is in {int(time_difference//60)}m {int(time_difference%60)}s',embeds=emb_list)	
				
	async def beige_watcher(self):
		subscription = await self.kit.subscribe("nation","update",{},self.beige_leave_handler)


	async def beige_leave_handler(self,nation_data):
		nation_data = nation_data.to_dict()
		#print(nation_data)
		#alert_channel = self.bot.get_channel(715222394318356541)
		#await alert_channel.send(f"TEST: [{nation_data['nation_name']}](<https://politicsandwar.com/nation/id={nation_data['id']}>) came out of beige just now")
		
		loot = await loot_calculator(nation_data['id'])
		if loot:
			nation_data['loot'] = int(loot[0])
		else:
			nation_data['loot'] = 'No loot info found'
		async with aiosqlite.connect("pnw.db") as db:
			db.row_factory = aiosqlite.Row
			async with db.execute("""
					SELECT beige_alerts.user_id, beige_alerts.all_nations,beige_alerts.alliances,beige_alerts.loot,beige_alerts.alert_time,
							all_nations_data.score
							FROM beige_alerts
							INNER JOIN registered_nations ON beige_alerts.user_id = registered_nations.discord_id
							INNER JOIN all_nations_data ON registered_nations.nation_id = all_nations_data.nation_id;""") as cursor:
					user_info = await cursor.fetchall()
		for user in user_info:
			if nation_data['score']>user['score']*0.75 and nation_data['score']<user['score']*2.5:
				if await self.is_alert_needed(nation_data,user):
					await self.send_alert(user,[nation_data])

async def setup(bot):
    await bot.add_cog(beige_alerts(bot))
