from discord.ext import commands,tasks
import aiosqlite
from datetime import datetime,timedelta,timezone,time
import discord
from scripts import nation_data_converter
from scripts.event_bus import bus
from bot import loot_calculator
from web_flask import beige_link
import pnwkit,logging,httpx
from discord.errors import Forbidden
from math import ceil
import asyncio

utc = timezone.utc
alert_times = [time(hour=i,minute=53,tzinfo=utc) for i in range(1,23,2)]
tc_times = [time(hour=i,minute=0,second=0,tzinfo=utc) for i in range(0,23,2)]

class beige_alerts(commands.Cog):
	def __init__(self,bot,):
		self.bot = bot
		self.bus = bus
		self.subscription = None
		self.nation_list = []
		self.kit = pnwkit.QueryKit("fb46570337e1dcdbb0d2")
		self.check_for_beigealerts.add_exception_type(KeyError)
		self.check_for_beigealerts.start()
		self.bus.connect('nation_data_updated',self.get_list_in_beige)
		self.disconnect_and_reconnect_beige_watcher.start()

	class MonitorFlags(commands.FlagConverter,delimiter= " ",prefix='-'):
		all_nations: bool = True
		alliances: str = 'Default'
		loot: int = 0
		time: int = 0
		downdec: int = 0

	@commands.Cog.listener()
	async def on_ready(self):
		# Start the watcher after the bot is ready
		logging.info("Beige watcher started.")
		await self.beige_watcher()

	async def get_list_in_beige(self):
		async with aiosqlite.connect('pnw.db') as db:
			async with db.execute('select nation_id from all_nations_data where beige_turns>0 and defensive_wars<>3') as cursor:
				nation_list = await cursor.fetchall()
		self.nation_list = [i[0] for i in nation_list]

	async def flags_parser(self,alliances,all_nations=1):
		
		if alliances!='Default':
			alliance_id = tuple(alliances.split(','))
			alliance_search = f"and alliance_id in {alliance_id}" if len(alliance_id)>1 else f"and alliance_id = {alliance_id[0]}"
			
		else:
			alliance_search = ""

		return alliance_search

	@commands.hybrid_command(name='beigealerts',with_app_command=True,description='Alerts about the targets leaving beige')
	async def beigealerts(self,ctx:commands.Context,*,flags:MonitorFlags):
		async with aiosqlite.connect('pnw.db') as db:
			if flags.alliances != 'Default':
				flags.all_nations = False
			await db.execute(f"INSERT OR REPLACE INTO beige_alerts values {(ctx.author.id,int(flags.all_nations),str(flags.alliances),flags.loot,flags.downdec,flags.time)}")
			await db.commit()
		
		

		alliance_search = await self.flags_parser(flags.alliances,flags.all_nations)
		endpoint = f"{ctx.author.id}"	
		unique_link = beige_link(endpoint, [alliance_search,flags.loot])
		
		await ctx.send(f"Alerts have been set. Use this link to plan when you need to be online:\n{unique_link}",ephemeral=True)

	@commands.hybrid_command(name='stopalerts',with_app_command=True,description='Stops beige alert dms for the user')
	async def stopalerts(self,ctx:commands.context):

		async with aiosqlite.connect('pnw.db') as db:
			await db.execute(f'delete from beige_alerts where user_id ={ctx.author.id}')
			await db.commit()

		await ctx.send("Alerts have been removed for you.")					

	async def is_alert_needed(self, target,user):
		if user['downdec']==0:
			if target['score']<user['score']*0.75 or target['score']>user['score']*2.5:
				return False
		else:
			if target['score']<(user['score']*0.75)-user['downdec'] or target['score']>user['score']*2.5:
				return False

		if not bool(user['all_nations']):
			if str(target['alliance_id']) not in (user['alliances'].split(',')):
				return False

		if target['loot']!='No loot info found':
			if user['loot']>int(target['loot']):
				return False
		
		return True

	async def demilitarizer(self,target,user):
		score_val = {"nukes":15,"missiles":5,"ships":1,"tanks":0.025,"aircraft":0.3}
		reduce_score = user["score"]-(target["score"]/0.75)
		keys = list(score_val.keys())
		i = 0
		result = {}

		while reduce_score>0 and i<len(keys):
			if user[keys[i]]!=0:
				no_of_unit = reduce_score/score_val[keys[i]]
				if no_of_unit<=user[keys[i]]:
					reduce_score -= ceil(no_of_unit) * score_val[keys[i]]
					result[keys[i]] = ceil(no_of_unit)
				else:
					reduce_score -= user[keys[i]] *score_val[keys[i]]	
					result[keys[i]] = user[keys[i]]
			i+=1
		if reduce_score>0:
			result['Note'] = 'Target too low, change downdec'
		return result


	@tasks.loop(time=alert_times,reconnect=True)
	async def check_for_beigealerts(self):
		async with aiosqlite.connect("pnw.db") as db:
			db.row_factory = aiosqlite.Row
			async with db.execute("""
				SELECT bankrecs.date,all_nations_data.nation_id, all_nations_data.nation, all_nations_data.alliance, all_nations_data.alliance_id, all_nations_data.score,all_nations_data.cities, all_nations_data.soldiers, all_nations_data.tanks, all_nations_data.aircraft, all_nations_data.ships, loot_data.war_end_date
				FROM all_nations_data
				LEFT JOIN loot_data on all_nations_data.nation_id = loot_data.nation_id
				left join bankrecs on all_nations_data.nation_id = bankrecs.nation_id
				WHERE beige_turns = 1 and defensive_wars<>3 and vmode=0""") as cursor:
				beige_data = await cursor.fetchall()
				beige_data.sort(key=lambda x:x['nation_id'])
			async with db.execute("""
				SELECT beige_alerts.user_id, beige_alerts.all_nations,beige_alerts.alliances,beige_alerts.loot,beige_alerts.downdec,beige_alerts.alert_time,
						all_nations_data.score,all_nations_data.soldiers, all_nations_data.tanks, all_nations_data.aircraft, all_nations_data.ships,all_nations_data.missiles,all_nations_data.nukes
						FROM beige_alerts
						INNER JOIN registered_nations ON beige_alerts.user_id = registered_nations.discord_id
						INNER JOIN all_nations_data ON registered_nations.nation_id = all_nations_data.nation_id;""") as cursor:
				user_info = await cursor.fetchall()
		updated_targets = []
		query = f"""{{nations(id:{[x['nation_id'] for x in beige_data]},first:500){{
		data{{
			cities{{infrastructure}}
			}}
		}} }}"""
		async with httpx.AsyncClient(timeout=20) as client:
			fetchdata = await client.post('https://api.politicsandwar.com/graphql?api_key=2bfb8817f934b00c5eb6',json={'query':query})
			fetchdata = fetchdata.json()['data']['nations']['data']
		
		for i in range(len(beige_data)):
			target = dict(beige_data[i])
			
			loot = await loot_calculator(target['nation_id'])
			if loot:
				target['loot'] = int(loot[0])
			else:
				target['loot'] = 'No loot info found'	
			if target['date']:
				target['last_deposit'] = nation_data_converter.time_converter(datetime.strptime(target['date'],'%Y-%m-%dT%H:%M:%S'))
			else:	
				target['last_deposit'] = 'No recent deposit'	
			
			target['avg_infra'] = round(sum([x['infrastructure'] for x in fetchdata[i]['cities']])/target['cities'],2) 
			updated_targets.append(target)		
		# Loop through each alert and evaluate its conditions
		if beige_data:
			for user in user_info:
				targets =[]
				for target in updated_targets:
					if await self.is_alert_needed(target,user):
						target['Demilitarize'] = None
						if target['score']<user['score']*0.75:
							target['Demilitarize'] = await self.demilitarizer(target,user)
						targets.append(target)
				if targets:
					try:
						logging.info(f"{user,{user['user_id']}} is set to recieve beige alerts.")
						await self.send_alert(user['user_id'],targets)
					except Forbidden:
						async with aiosqlite.connect('pnw.db') as db:
							await db.execute(f'delete from beige_alerts where user_id ={user}')
							await db.commit()
			

	async def get_user_safe(self, user_id):
		user = self.bot.get_user(user_id)
		if user:
			return user

		for _ in range(3):  # retry 3 times
			try:
				return await self.bot.fetch_user(user_id)
			except discord.DiscordServerError:
				await asyncio.sleep(2)

		return None			

	async def send_alert(self,user,targets,alert='normal'):
		dm_channel = await self.get_user_safe(user)
		if not dm_channel:
			logging.info(f'Ran into discord server error for user {user}')
			return
		emb_list = []
		warn = ""
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
			if target['Demilitarize']:
				lines = []
				items = list(target['Demilitarize'].items())

				for i in range(0, len(items), 2):
					left = items[i]
					right = items[i + 1] if i + 1 < len(items) else None

					left_str = f"{left[0].capitalize()}: {left[1]:<8,}"

					if right:
						right_str = f"{right[0].capitalize()}: {right[1]:<8,}"
						lines.append(f"{left_str}{right_str}")
					else:
						lines.append(left_str)

				demili_text = "```js\n" + "\n".join(lines) + "```"

				embed.add_field(
					name="DeCom info",
					value=demili_text,
					inline=False
				)
				warn = "⚠️ Consult with milcom before decomissioning any units ⚠️\n"

			emb_list.append(embed)
		now = datetime.now(timezone.utc)
		next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0).timestamp()
		
		message = f'These nations are coming out of beige next turn which is <t:{int(next_hour)}:R>'
		if alert!='normal':
			message = 'This nation left beige early:'
		for i in range(0,len(emb_list),10):
			await dm_channel.send(f'{warn}{message}',embeds=emb_list[i:i+10])	
	
	
	@tasks.loop(time=tc_times,reconnect=True)
	async def disconnect_and_reconnect_beige_watcher(self):
		await self.subscription.unsubscribe()
		logging.info(f"Unsubscribed at {datetime.now(timezone.utc).strftime('%H:%M:%S')}" )
		await asyncio.sleep(600)
		if datetime.now(timezone.utc).hour==0:
			await asyncio.sleep(1200)

		await bus.emit('update_nations')
		self.subscription = await self.kit.subscribe("nation","update",{"include":["color","id"]},self.beige_leave_handler)
		logging.info(f"Resubscribed at {datetime.now(timezone.utc).strftime('%H:%M:%S')}")

	async def beige_watcher(self):
		self.subscription = await self.kit.subscribe("nation","update",{"include":["color","id","beige_turns"]},self.beige_leave_handler)


	async def beige_leave_handler(self,nation_data):
		if nation_data.id in self.nation_list:
			if nation_data.color != 'beige':
				self.nation_list.remove(nation_data.id)
				try:
					logging.info(f"{nation_data.id} left beige early with color {nation_data.color} and beige_turns {nation_data.beige_turns}")
				except:
					logging.info(f"{nation_data.id} left beige early with color {nation_data.color} and missing beige_turns field")
				async with aiosqlite.connect('pnw.db') as db:
					db.row_factory = aiosqlite.Row
					async with db.execute(f"""SELECT bankrecs.date,all_nations_data.nation_id, all_nations_data.nation, all_nations_data.alliance, all_nations_data.alliance_id, all_nations_data.score,all_nations_data.cities, all_nations_data.soldiers, all_nations_data.tanks, all_nations_data.aircraft, all_nations_data.ships, loot_data.war_end_date
					FROM all_nations_data
					LEFT JOIN bankrecs on all_nations_data.nation_id = bankrecs.nation_id
					LEFT JOIN loot_data on all_nations_data.nation_id = loot_data.nation_id
					where all_nations_data.nation_id={nation_data.id}""") as cursor:
						target =  await cursor.fetchone()
						if not target:
							logging.info('target is none')
							return
						target = dict(target)
					async with db.execute("""
				SELECT beige_alerts.user_id, beige_alerts.all_nations,beige_alerts.alliances,beige_alerts.loot,beige_alerts.downdec,beige_alerts.alert_time,
						all_nations_data.score,all_nations_data.soldiers, all_nations_data.tanks, all_nations_data.aircraft, all_nations_data.ships,all_nations_data.missiles,all_nations_data.nukes
						FROM beige_alerts
						INNER JOIN registered_nations ON beige_alerts.user_id = registered_nations.discord_id
						INNER JOIN all_nations_data ON registered_nations.nation_id = all_nations_data.nation_id;""") as cursor:
						user_info = await cursor.fetchall()

				query = f"""{{nations(id:{nation_data.id}){{
						data{{
							cities{{infrastructure}}
							}}
						}}  }}"""
				async with httpx.AsyncClient(timeout=20) as client:
					fetchdata = await client.post('https://api.politicsandwar.com/graphql?api_key=2bfb8817f934b00c5eb6',json={'query':query})
					citydata = fetchdata.json()['data']['nations']['data'][0]
				
				loot = await loot_calculator(target['nation_id'])
				if loot:
					target['loot'] = int(loot[0])
				else:
					target['loot'] = 'No loot info found'	
				if target['date']:
					target['last_deposit'] = nation_data_converter.time_converter(datetime.strptime(target['date'],'%Y-%m-%dT%H:%M:%S'))
				else:	
					target['last_deposit'] = 'No recent deposit'	
				
				target['avg_infra'] = round(sum([x['infrastructure'] for x in citydata['cities']])/target['cities'],2) 
				
				for user in user_info:
					if await self.is_alert_needed(target,user):
						target['Demilitarize'] = None
						if target['score']<user['score']*0.75:
							target['Demilitarize'] = await self.demilitarizer(target,user)
						try:
							logging.info(f"{user,{user['user_id']}} is set to recieve beige alerts.")
							await self.send_alert(user['user_id'],[target],alert='left_beige')
						except Forbidden:
							async with aiosqlite.connect('pnw.db') as db:
								await db.execute(f'delete from beige_alerts where user_id ={user}')
								await db.commit()

					
async def setup(bot):
    await bot.add_cog(beige_alerts(bot))