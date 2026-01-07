import os,discord,logging,re
from discord.ext import commands
import typing
from scripts import nation_data_converter,sheets,war_stats
from scripts.db_tasks import db_tasks
from scripts.bot_bg_tasks import Bot_bg_Tasks	
from scripts.pagination import Pagination
from datetime import datetime,timedelta,timezone
import aiosqlite,asyncio,httpx
import numpy as np
import matplotlib.pyplot as plt
from itertools import combinations_with_replacement
from commands.role_view import MyPersistentView
from commands.best_manu_view import ManuPersistentView
from scripts.trade_bot import trade_watcher
from dotenv import load_dotenv
import web_flask
from math import ceil

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(filename='log.txt',	level=logging.INFO) #	
aiosqlite.threadsafety=1
load_dotenv()

async def update_registered_nations(author_id,author_name,nation_id):
	async with aiosqlite.connect('pnw.db') as db:
		data_to_be_inserted=("insert into registered_nations values(%s,'%s',%s) on conflict(discord_id) do update set user_name='%s',nation_id=%s") % (author_id,author_name,nation_id,author_name,nation_id)
		await db.execute(data_to_be_inserted)
		await db.commit()	
pass	

async def targets(war_range,inactivity_time,aa,beige,beige_turns,result_size=None):	
	async with aiosqlite.connect('pnw.db') as db:
		date=datetime.now(timezone.utc).replace(microsecond=0)
		date = date -timedelta(days=inactivity_time)
		search_list1 = ','.join([f'loot_data.{x}' for x in [ 'money', 'food', 'coal', 'oil', 'uranium', 'lead', 'iron', 'bauxite', 'gasoline', 'munitions', 'steel', 'aluminum','war_end_date']])
		search_list2 = ','.join([f'all_nations_data.{x}' for x in ['nation_id','nation','alliance','alliance_id','cities','beige_turns','soldiers', 'tanks', 'aircraft', 'ships','missiles','nukes','last_active','defensive_wars','alliance_position']])
		targets_list = f"select {search_list1},{search_list2} from all_nations_data left join loot_data on all_nations_data.nation_id =loot_data.nation_id where score>{war_range[0]} and score<{war_range[1]} {beige} and vmode=0 and defensive_wars<>3 {aa} {beige_turns} and date(last_active)<'{date}'"
		logging.info(targets_list)
		db.row_factory =aiosqlite.Row
		cursor = await db.execute(targets_list)

		all_targets= await cursor.fetchall()
		all_targets = [dict(x) for x in all_targets]
		await cursor.close()
		prices=await get_prices(db)
	prices = dict(prices)
	for target_nation in all_targets:
		if not target_nation["money"]:
			target_nation["beige_loot"] = "No loot data"
			continue
		beige_amount = target_nation["money"]*0.14
		for rss,price in prices.items():
			beige_amount += target_nation[rss]*0.14*price
		target_nation["beige_loot"] = round(beige_amount,2)
	all_targets.sort(key=lambda x: (x["beige_loot"] == "No loot found", float(x["beige_loot"]) if x["beige_loot"] != "No loot data" else 0), reverse=True)
	all_targets=all_targets[:result_size]
	deposit_data_list=await last_bank_rec([[x["nation_id"],x["nation"]] for x in all_targets])
	for x in range(len(all_targets)):
		if deposit_data_list[x]!='N/A':
			all_targets[x]["last_deposit_date"] = nation_data_converter.time_converter(datetime.strptime(deposit_data_list[x],"%Y-%m-%dT%H:%M:%S"))
		else:
			all_targets[x]["last_deposit_date"] = 'N/A'	
		if all_targets[x]["war_end_date"]!=None:
			all_targets[x]["war_end_date"] = nation_data_converter.time_converter(datetime.strptime(all_targets[x]["war_end_date"],"%Y-%m-%dT%H:%M:%S"))
		else: 
			all_targets[x]["war_end_date"] = "No war data found"	
		all_targets[x]["last_active"] = nation_data_converter.time_converter(datetime.strptime(all_targets[x]["last_active"],"%Y-%m-%d %H:%M:%S"))																   
		all_targets[x]["alliance_position"] = nation_data_converter.position(all_targets[x]["alliance_position"])
	return all_targets
pass


async def last_bank_rec(nation_list):
	query=''
	results=[]
	i=0
	async with httpx.AsyncClient() as client:
		for nation in nation_list:
			if len(query)>9900:
				query=f"{{ {query} }}"
				fetchdata = await client.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':query})
				results.append(fetchdata.json()['data'])
				query=''
			query=f"""{query}i{i}:bankrecs(sid:{nation[0]},orderBy:{{column:DATE,order:DESC}},first:1,rtype:2){{data{{date}}}}"""
			i+=1	
		query=f"{{ {query} }}"
		fetchdata = await client.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':query})
		results.append(fetchdata.json()['data'])	
	fetchdata= {key:values for d in results for key,values in d.items()}
	bankdata=[]	
	for i in range(len(nation_list)):	
		nation_data = fetchdata[f"i{i}"]["data"]
		if not nation_data:
			bankdata.append('N/A')
		else:
			bankdata.append((nation_data[0]['date']).split('+')[0])
	return bankdata

async def get_prices(db):
	cursor= await db.execute("select * from trade_prices")
	price= await cursor.fetchone()
	await cursor.close()
	return price	
pass

async def beige_calculator(params,resistance,reverse):
	cost_dict = {10:(3,'Gd'),12:(4,'Ar'),14:(4,'Nv')}
	if params !=None:
		params = params.split(' ')
		for param in params:
			if param =="+m":
				cost_dict[18]=(8,'Ms')
			elif param=="+nu":
				cost_dict[25]=(12,'Nu')
			elif param=="-g":
				cost_dict.pop(10)
			elif param=="-a":
				cost_dict.pop(12)
			elif param=="-nv":
				cost_dict.pop(14)	
	comb = []
	for x in cost_dict.keys():
		comb += list(combinations_with_replacement(cost_dict.keys(),int(resistance/x +1)))

	results=[]
	for values in comb:
		if sum(values)>=resistance and sum(values[:-1])<resistance:
			cost = 0
			for damage in values:
				cost += cost_dict[damage][0]
			results.append((comb.index(values),cost))
	results = list(set(results))
	results.sort(key=lambda x:x[1],reverse=reverse)
	text_first_line = '\t'.join([x[1] for x in cost_dict.values()])
	text = f"{text_first_line}\tTurns"
	
	for x in range(5):
		if x<len(results):
			text += "\n"
			for attacks in cost_dict.keys():
				text += f"{comb[results[x][0]].count(attacks)} \t"

			text +=	f"{results[x][1]}"

	return text	

def simulate_casualities(attacker,defender,multiplier):
	size=(10000,3)
	att_roll = np.random.randint(0.4*attacker*multiplier,(attacker+1)*multiplier,size=size)
	def_roll = np.random.randint(0.4*defender*multiplier,(defender+1)*multiplier,size=size)
	att_casualties=np.round(np.average(np.sum(def_roll*0.01,axis=1)),2)
	def_casualties=np.round(np.average(np.sum(att_roll*0.018337,axis=1)),2)

	return att_casualties,def_casualties

def simulate_war(attacker,defender,multiplier):
	size=(10000,3)
	attacker = attacker**0.75
	defender = defender**0.75
	att_roll = np.random.randint(0.4*attacker*multiplier,(attacker+1)*multiplier,size=size)
	def_roll = np.random.randint(0.4*defender*multiplier,(defender+1)*multiplier,size=size)

	win_outcomes=np.greater(att_roll,def_roll)

	wins = np.round(np.bincount(np.sum(win_outcomes,axis=1))/size[0]*100,2)

	return wins

async def loot_from_text(message,length_of_param):
	find_stuffs_orig = ['food', 'coal', 'oil', 'uranium', 'lead', 'iron', 'bauxite', 'gasoline', 'munitions', 'steel', 'aluminum']
	find_stuffs = [f"[,.0-9]{{{length_of_param},}} {x}" for x in find_stuffs_orig]
	find_stuffs.insert(0,f'\$[,.0-9]{{{length_of_param},}} ')
	actual_loot =[]
	for loot in find_stuffs:
		loot_info = re.findall(loot,message,flags=re.IGNORECASE)	
		if len(loot_info)!=0:
			actual_loot.append(loot_info[0].split(' ')[0].replace(',','').replace('$',''))
		else:
			actual_loot.append(0)  
	async with aiosqlite.connect('pnw.db') as db:
		prices = await get_prices(db)

	return actual_loot,prices

async def loot_calculator(nation_id):
	async with aiosqlite.connect('pnw.db') as db:
		prices = await get_prices(db)	
		db.row_factory =aiosqlite.Row
		async with db.execute(f'select * from loot_data where nation_id={nation_id}') as cursor:
			loot = await cursor.fetchone()
			loot = list(loot)
		async with db.execute(f'select war_policy from all_nations_data where nation_id ={nation_id}') as cursor:	
			war_policy = await cursor.fetchone()
	if loot!=None:
		policy_modifer = 1 
		if war_policy['war_policy'] ==5:
			policy_modifer = 1.4
		total_worth = loot[2]*0.14/policy_modifer
		for x in range(0,len(prices)):
			total_worth+= (int(loot[x+3]*0.14/policy_modifer)*prices[x])
			loot[x+3] = loot[x+3]/policy_modifer
		return (total_worth,loot)
	else:
		return None 

async def monitor_targets(war_range,alliance_search,loot,search_only=False):
	search_list1 = ','.join([f'loot_data.{x}' for x in ['nation_id', 'money', 'food', 'coal', 'oil', 'uranium', 'lead', 'iron', 'bauxite', 'gasoline', 'munitions', 'steel', 'aluminum','war_end_date']])
	search_list2 = ','.join([f'all_nations_data.{x}' for x in ['nation','alliance','alliance_id','score','cities','beige_turns','soldiers', 'tanks', 'aircraft', 'ships','missiles','nukes','last_active','defensive_wars','alliance_position']])
	targets_list = f"select {search_list1},{search_list2} from loot_data inner join all_nations_data on loot_data.nation_id =all_nations_data.nation_id where vmode=0 and defensive_wars<>3 and color=0 {war_range} {alliance_search}"
	async with aiosqlite.connect('pnw.db') as db:
		db.row_factory =aiosqlite.Row
		cursor = await db.execute(targets_list)

		all_targets= await cursor.fetchall()
		all_targets = [dict(x) for x in all_targets]
		await cursor.close()
		prices=await get_prices(db)
	prices = dict(prices)
	for target_nation in all_targets:
		beige_amount = target_nation["money"]*0.14
		for rss,price in prices.items():
			beige_amount += target_nation[rss]*0.14*price
		target_nation["beige_loot"] = round(beige_amount,2)
	all_targets = [x for x in all_targets if x["beige_loot"]>=loot]	
	if search_only:
		all_targets.sort(key=lambda x:x["beige_loot"],reverse=True)
		deposit_data_list=await last_bank_rec([[x["nation_id"],x["nation"]] for x in all_targets])
		for x in range(len(all_targets)):
			if deposit_data_list[x]!='N/A':
				all_targets[x]["last_deposit_date"] = nation_data_converter.time_converter(datetime.strptime(deposit_data_list[x],"%Y-%m-%dT%H:%M:%S"))
			else:
				all_targets[x]["last_deposit_date"] = 'N/A'	
			all_targets[x]["war_end_date"] = nation_data_converter.time_converter(datetime.strptime(all_targets[x]["war_end_date"],"%Y-%m-%dT%H:%M:%S"))
			all_targets[x]["last_active"] = nation_data_converter.time_converter(datetime.strptime(all_targets[x]["last_active"],"%Y-%m-%d %H:%M:%S"))																   
			all_targets[x]["alliance_position"] = nation_data_converter.position(all_targets[x]["alliance_position"])
		
	return all_targets


def is_guild(ctx):
	if ctx.guild is None:
		return False
	elif ctx.guild.id in [1082151511892693055,1367766815941328907]:
		wap_role_ids = {1146498346245181520, 1082777885372330064,1090430905870463058}
		user_roles = {role.id for role in ctx.author.roles}
		if wap_role_ids.intersection(user_roles):
			return True
		else:
			return False
	else: 
		return ctx.guild

async def setup_hook():
	async with aiosqlite.connect('pnw.db') as db:
		async with db.execute('select * from persistent_views') as cursor:
			views = await cursor.fetchall()
	for view in views:
		guild = await client.fetch_guild(view[0])
		roles = view[1].split(',')
		if roles:
			roles = [guild.get_role(int(role)) for role in roles]
			client.add_view(MyPersistentView(roles),message_id= view[2])
		else:
			client.add_view(ManuPersistentView(),message_id= view[2])

graphql_link='https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab'
intents = discord.Intents.default()	
intents.message_content = True
client=commands.AutoShardedBot(command_prefix=os.getenv('command_prefix'),help_command=None,intents=intents)
activity = discord.CustomActivity(name="🐧 NOOT NOOT 🐧 ")
#client.add_check(is_guild)
client.setup_hook = setup_hook
client.updater= db_tasks()

@client.event
async def on_ready():
	logging.info('Bot is ready')
	client.updater.run()
	start_trade = trade_watcher(client=client)
	Bot_bg_Tasks(client)
	
	await start_trade.start()
	await client.change_presence(status=discord.Status.online, activity=activity)
	await client.load_extension("commands.help")
	await client.load_extension("commands.nation_audit")
	await client.load_extension("commands.beigealerts")
	cog = client.get_cog("beige_alerts")
	await cog.on_ready()

@client.event
async def on_command_error(ctx, error):
	logging.warning(f"Discord Command Error:{error}")
	if isinstance(error, commands.CheckFailure):
		await ctx.send("Greetings Outsider,\nAll commands can only be used in the WAP server\nNOOT NOOT")
	else:
		raise error

@commands.is_owner()
@client.command()
async def guilds(ctx):
	embed=discord.Embed()
	embed.title='Servers'
	embed.description='The list of the alliances the bot is present in:'
	counter=1
	async for guild in client.fetch_guilds(limit=150):
		embed.add_field(name=f'{counter}.{guild.name}',value=f'Server ID:{guild.id}',inline=False)
		counter=counter+1
	await ctx.send(embed=embed)	

@client.hybrid_command(name="loot",with_app_command=True,description="Amount of loot you would get from the target nation considering a raid war and pirate war policy")
async def loot(ctx:commands.Context,*,nation_id:str):
	nation_id=await nation_data_converter.nation_id_finder(ctx,nation_id)
	result = await loot_calculator(nation_id)	
	if result!=None:
		embed=discord.Embed()
		embed.title=f'Loot info for {await nation_data_converter.get_unregistered("nation",nation_id)}'
		list_of_things_to_find=['Money','Food','Coal','Oil','Uranium','Lead','Iron','Bauxite','Gasoline','Munitions','Steel','Aluminum']
		for x in range(0,len(list_of_things_to_find)):
			embed.add_field(name=list_of_things_to_find[x],value='{:,}'.format(int(result[1][x+2]*0.14)),inline=True)
		embed.add_field(name="Total monetary value",value=f'${result[0]:,}',inline=True)	
		time_diff = nation_data_converter.time_converter(datetime.strptime(result[1][-1],"%Y-%m-%dT%H:%M:%S"))	
		add='war loss'
		if result[1][0]==0:
			add='spy op'		
		embed.set_footer(text=f'Based on {add} from {time_diff}\nAssuming raid war and pirate war policy')	
		await ctx.send(embed=embed)
	else:
		await ctx.send("No recent spy or war loss data found")		

class RaidFlags(commands.FlagConverter,delimiter= " ",prefix='-'):
	all_nations: bool = False
	inactivity_days: int = 0
	alliances: str = 'Default'
	beige: bool = True
	beige_turns: int = 216
	result: str = 'web'
	fake_score: int = 0 
	size:int = 50

@client.hybrid_command(name="raid",with_app_command=True,description="Finds the best raiding targets")
async def raid(ctx:commands.Context, *,flags:RaidFlags):

	score= await nation_data_converter.get('score',ctx.author.id)
	page1=discord.Embed()
	if score!=None:
		if flags.fake_score!=0:
			score = flags.fake_score
		flags.alliances=flags.alliances.split(',')
		date=datetime.now(timezone.utc).replace(microsecond=0)
		date = date -timedelta(days=10)
		async with aiosqlite.connect('pnw.db') as db:
			async with db.execute('select * from safe_aa') as cursor:
				safe_aa = await cursor.fetchall()
			safe_aa = tuple([x[0] for x in safe_aa])
		if flags.beige:
			flags.beige_turns=f'and beige_turns<{flags.beige_turns}'
		else:
			flags.beige_turns=''			
		flags.beige='' if flags.beige==True else 'and color<>0'
		if flags.alliances==['Default'] and flags.all_nations==False:
			flags.alliances=f"and (alliance_id not in {safe_aa} or (alliance_id in {safe_aa} and (alliance_position=1 or date(last_active)<'{date}')))"
		elif flags.all_nations==False:
			flags.alliances=tuple(flags.alliances)
			if len(flags.alliances)!=1:
				flags.alliances = f'and alliance_id in {flags.alliances}'
			else:
				flags.alliances	= f'and alliance_id = {flags.alliances[0]}'
		else:
			flags.alliances=''		
		war_range=score*0.75,score*2.5
		if flags.result =="embed":
			list_of_targets=await targets(war_range,flags.inactivity_days,flags.alliances,flags.beige,flags.beige_turns,result_size=9)
			async def get_page(page: int):
				L=3
				emb = discord.Embed(title="Targets", description="")
				offset = (page-1) * L
				i=1
				for target in list_of_targets[offset:offset+L]:
					loot = f"Loot: ${target['beige_loot']:,}"
					emb.add_field(name=f'{i}. https://politicsandwar.com/nation/id={(target["nation_id"])}',value=f'{loot}',inline=False)
					emb.add_field(name='Alliance',value=target["alliance"],inline=True)
					if target["beige_turns"]!=0:
						emb.add_field(name='Beige',value=f'{target["beige_turns"]} turns',inline=True)	
					emb.add_field(name='Soldiers',value=target["soldiers"],inline=True)
					emb.add_field(name='Tanks',value=target["tanks"],inline=True)
					emb.add_field(name='Aircrafts',value=target["aircraft"],inline=True)
					emb.add_field(name='Ships',value=target["ships"],inline=True)
					emb.add_field(name='Last bank deposit',value=target["last_deposit_date"],inline=True)
					i+=1
				emb.set_author(name=f"Requested by {ctx.author}")
				n = Pagination.compute_total_pages(len(list_of_targets), L)
				emb.set_footer(text=f"Page {page} from {n}")
				return emb, n

			await Pagination(ctx.interaction, get_page).navigate()
		elif flags.result=='sheets':
			if ctx.interaction:
				await ctx.interaction.response.defer(thinking='Calculating')
			list_of_targets=await targets(war_range,flags.inactivity_days,flags.alliances,flags.beige,flags.beige_turns,result_size=flags.size)
			keys = ['beige_loot','war_end_date','alliance','cities','beige_turns','soldiers','tanks','aircraft','ships','last_active','last_deposit_date']
			for i in range(len(list_of_targets)):
				recreate_target = [f'=HYPERLINK("https://politicsandwar.com/nation/id={list_of_targets[i]["nation_id"]}","{list_of_targets[i]["nation"]}")']
				recreate_target.extend([list_of_targets[i][key] for key in keys])
				list_of_targets[i] = recreate_target
			list_of_targets.insert(0,['Nation','Loot','War loss date','Alliance','Cities','Beige Turns','Soldiers','Tanks','Aircrafts','Ships','Last Active','Last Bank Deposit'])
			sheetID=sheets.create('Raid Targets',[{"properties":{"sheetId":0,'title':'Targets'}}])
			sheets.write_ranges(sheetID,f'Targets!A1:L{len(list_of_targets)}',list_of_targets)
			if ctx.interaction:
				await ctx.interaction.followup.send(f'https://docs.google.com/spreadsheets/d/{sheetID}')
			else:	
				await ctx.send(f'https://docs.google.com/spreadsheets/d/{sheetID}')

		elif flags.result=='web':
			endpoint = str(ctx.message.author)
			endpoint = re.sub('[\W_]+', '', endpoint)
			logging.info([war_range,flags.inactivity_days,flags.alliances,flags.beige,flags.beige_turns,flags.size])
			unique_link = web_flask.generate_link(endpoint, [war_range,flags.inactivity_days,flags.alliances,flags.beige,flags.beige_turns,flags.size])
			await ctx.send(unique_link)
	else:
		page1.title='Register'
		page1.description='Usage : `;register <nation id|nation link>`'
		await ctx.send(content="You must be registered to use this command",embed=page1)	
			
@client.hybrid_command(name="register",with_app_command=True,description="Registers you to the bot")
async def register(ctx,link):
	if link.startswith('http'):
		nation_id=int(link[37:])
	else:
		nation_id=link
	
	async with httpx.AsyncClient() as client:
		query= f"{{nations(id:{nation_id}){{ data{{discord}} }} }}"
		fetchdata = await client.post(graphql_link,json={'query':query})
		fetchdata = fetchdata.json()['data']['nations']['data'][0]
	if fetchdata["discord"].capitalize()==str(ctx.message.author).capitalize():	
		await update_registered_nations(ctx.author.id,ctx.message.author,nation_id)
		await ctx.send("Successfully registered")		
	else:
		await ctx.send(f"Go to https://politicsandwar.com/nation/edit \nPut your username `{ctx.message.author}` in the discord username section at the bottom.\nClick save & try again.")
		

@client.hybrid_command(name="wars",with_app_command=True,description="Fetchs the wars the nation is currently in")
async def wars(ctx,*,_id=None):
	if _id==None:
		_id=str(ctx.author.id)
	nation_id=await nation_data_converter.nation_id_finder(ctx,_id)
	query=f"""{{
		wars(nation_id:{nation_id},days_ago:5){{data{{
			id,end_date
			att_id,def_id,att_resistance,def_resistance,att_alliance_id,def_alliance_id
			war_type,ground_control,air_superiority,naval_blockade
			
  			}} }}
		
		nations(id:{nation_id}){{data{{
			nation_name,num_cities,alliance{{name}},alliance_id
			beige_turns,soldiers,tanks,aircraft,ships,missiles,nukes,spies}}
		}}
		}}"""
	async with httpx.AsyncClient() as client:
		fetchdata=await client.post(graphql_link,json={'query':query})
		fetchdata = fetchdata.json()['data']
	war_data = fetchdata['wars']['data']
	nation_data = fetchdata['nations']['data'][0]
	emb = discord.Embed()
	emb.title = f'War info for {nation_data["nation_name"]}'
	emb.description =(f'Nation: [{nation_data["nation_name"]}](https://politicsandwar.com/nation/id={nation_id})\n'
					f'Cities: {nation_data["num_cities"]}\n'
					f'Alliance: [{nation_data["alliance"]["name"]}](https://politicsandwar.com/alliance/id={nation_data["alliance_id"]})\n'
					f'Beige Turns: {nation_data["beige_turns"]}')
	
	emb.add_field(name='Army',
			   value=("```js\n"
					f"Soldiers: {nation_data['soldiers']:<8,}"
					f"Tanks: {nation_data['tanks']:<8,}\n"
					f"Aircraft: {nation_data['aircraft']:<8,}"
					f"Ships: {nation_data['ships']:<8,}\n"
					f"Missiles: {nation_data['missiles']:<8,}"
					f"Nukes: {nation_data['nukes']:<8,}\n"
					f"Spies: {nation_data['spies']:<8,}```"),
					inline=False)

	count_off,count_def=1,1
	off_text,def_text="",""
	for war in war_data: 
		if int(war['att_id'])==nation_id:
			off_text=(f"{off_text}{count_off}. [{await nation_data_converter.get_unregistered('nation',war['def_id'])}](https://politicsandwar.com/nation/id={war['def_id']})  "
		 			f"`AR:{war['att_resistance']}` `DR:{war['def_resistance']}`\n"
					f"Alliance: *{await nation_data_converter.get_unregistered('alliance',war['def_id'])}*\n")
			count_off+=1
		else:
			def_text=(f"{def_text}{count_def}. [{await nation_data_converter.get_unregistered('nation',war['att_id'])}](https://politicsandwar.com/nation/id={war['att_id']})  "
		 			f"`DR:{war['def_resistance']}` `AR:{war['att_resistance']}`\n"
					f"Alliance: *{await nation_data_converter.get_unregistered('alliance',war['att_id'])}*\n")
			count_def+=1
		
	if off_text!="":
		emb.add_field(name='Offensive wars',value=off_text,inline=False)
	if def_text!="":
		emb.add_field(name="Defensive wars",value=def_text,inline=False)	
			
	await ctx.send(embed=emb)	

@client.hybrid_command(name="who",with_app_command=True,description="Gives info on the given nation or user")
async def who(ctx,*,discord_name):
	nation_id=await nation_data_converter.nation_id_finder(ctx,discord_name)
	nation_data = await nation_data_converter.get_unregistered('*',nation_id)
	discord_id=await nation_data_converter.get('discord_id',nation_id,'registered_nations.nation_id')
	if isinstance(nation_data,tuple):
		embed=discord.Embed()
		embed.title=f'{nation_data[1]}'
		embed.url=f'https://politicsandwar.com/nation/id={nation_data[0]}'
		if discord_id!=None:
			embed.add_field(name='Discord id',value=f'<@{discord_id}>',inline=True)	
		embed.add_field(name='Score',value=nation_data[13],inline=True)
		embed.add_field(name='Offensive War Range',value=f'{int(0.75*nation_data[13])}-{int(2.75*nation_data[13])}',inline=True)
		embed.add_field(name='Defensive War Range',value=f'{int(nation_data[13]/2.75)}-{int(nation_data[13]/0.75)}',inline=True)
		embed.add_field(name='Cities',value=nation_data[10],inline=True)
		embed.add_field(name='Color',value=nation_data_converter.color(nation_data[6]),inline=True)
		if nation_data[6]==0:
			embed.add_field(name='Beige Turns',value=f'{nation_data[16]} turns',inline=True)
		embed.add_field(name='Continent',value=nation_data_converter.continent(nation_data[3]),inline=True)
		if nation_data[7]!=0:
			embed.add_field(name='Alliance',value=f"[{nation_data[8]}](https://politicsandwar.com/alliance/id={nation_data[7]})",inline=True)
		else:
			embed.add_field(name='Alliance',value=f"{nation_data[8]}",inline=True)
		embed.add_field(name='Domestic policy',value=nation_data_converter.domestic_policy(nation_data[5]),inline=True)
		embed.add_field(name='War policy',value=nation_data_converter.war_policy(nation_data[4]),inline=True)
		embed.add_field(name='Offensive wars',value=nation_data[11],inline=True)
		embed.add_field(name='Defensive wars',value=nation_data[12],inline=True)
		embed.add_field(name='Soldiers',value=nation_data[19],inline=True)
		embed.add_field(name='Tanks',value=nation_data[20],inline=True)
		embed.add_field(name='Aircrafts',value=nation_data[21],inline=True)
		embed.add_field(name='Ships',value=nation_data[22],inline=True)
		embed.add_field(name='Missiles',value=nation_data[23],inline=True)
		embed.add_field(name='Nukes',value=nation_data[24],inline=True)
		await ctx.send(embed=embed)
	else:
		alliance_id= await nation_data_converter.aa_finder(discord_name)
		alliance_data = await nation_data_converter.get_unregistered('cities,offensive_wars,defensive_wars,score,soldiers,tanks,aircraft,ships,missiles,nukes',alliance_id,'alliance_position<>1 and alliance_id',True)
		if alliance_id!=[]:	
			total_stats=[0 for x in alliance_data[0]]
			for y in range(0,len(alliance_data)):
				temp=[x for x in alliance_data[y]]
				total_stats=[total_stats[i]+temp[i] for i in range(0,len(temp))]
			embed=discord.Embed()
			embed.title=f"{(await nation_data_converter.get_unregistered('alliance',alliance_id,'alliance_id'))}({len(alliance_data)} nations)"
			embed.url=f'https://politicsandwar.com/alliance/id={alliance_id}'
			just_list=['Cities','Offensive Wars','Defensive Wars','Score','Soldiers','Tanks','Aircraft','Ships','Missiles','Nukes']	
			for x in range(0,len(just_list)):
				embed.add_field(name=just_list[x],value=total_stats[x],inline=True)
			await ctx.send(embed=embed)				
		else:			
			await ctx.send('Invalid nation/allinace')
		
@client.tree.command(name='war_vis',description="Provides a sheet")
async def war_vis(interaction: discord.Interaction, allies:str,enemies:str):
	await interaction.response.defer(thinking='Calculating the statistics')
	allies=tuple(allies.split(','))
	enemies=tuple(enemies.split(','))
	sheetID=sheets.create('War Visualizer',[{"properties":{"sheetId":0,'title':'Overview'}},{"properties":{"sheetId":1,'title':'Allies'}},{"properties":{"sheetId":2,'title':'Enemies'}}])
	asyncio.create_task(war_stats.war_vis_sheet(allies,enemies,sheets,sheetID))
	await interaction.followup.send(f'https://docs.google.com/spreadsheets/d/{sheetID}')

@client.hybrid_command(name='ground', with_app_command=True,description="Simulate a ground attack")
async def ground(ctx: commands.Context, att_soldiers:int,att_tanks:int,def_soldiers:int,def_tanks:int,population:int= 0,att_use_munitions:bool= True,def_use_munitions:bool= True):
	att_soldiers_multiplier=1.75 if att_use_munitions else 1
	def_soldiers_multiplier=1.75 if def_use_munitions else 1
	size=(10000,3)
	atsr = np.random.randint(0.4*att_soldiers*att_soldiers_multiplier,(att_soldiers+1)*att_soldiers_multiplier,size=size)
	attr = np.random.randint(0.4*att_tanks*40,(att_tanks+1)*40,size=size)

	dfsr = np.random.randint(0.4*def_soldiers*def_soldiers_multiplier,(def_soldiers+1)*def_soldiers_multiplier,size=size)
	dftr = np.random.randint(0.4*def_tanks*40,(def_tanks+1)*40,size=size)

	att_army_value=atsr+attr
	def_army_value=dfsr+dftr+population/400
	outcomes=np.greater(att_army_value,def_army_value)

	ats_causalities=np.round(np.average(np.sum(dfsr*0.0084+dftr*0.0092,axis=1)),2)
	dfs_causalities=np.round(np.average(np.sum(atsr*0.0084+attr*0.0092,axis=1)),2)

	att_causalities=np.round(np.average(np.sum(np.where(outcomes,dfsr*0.0004060606+dftr*0.00066666666,dfsr*0.00043225806+dftr*0.00070967741),axis=1)),2)
	dft_causalities=np.round(np.average(np.sum(np.where(outcomes,atsr*0.00043225806+attr*0.00070967741,atsr*0.0004060606+attr*0.00066666666),axis=1)),2)
	
	att_soldiers_modified = att_soldiers ** (3/4)
	att_tanks_modified = att_tanks ** (3/4)
	def_soldiers_modified = def_soldiers ** (3/4)
	def_tanks_modified = def_tanks ** (3/4)

	atsr = np.random.randint(int(0.4 * att_soldiers_modified * att_soldiers_multiplier), int((att_soldiers_modified + 1) * att_soldiers_multiplier), size=size)
	attr = np.random.randint(int(0.4 * att_tanks_modified * 40), int((att_tanks_modified + 1) * 40), size=size)

	dfsr = np.random.randint(int(0.4 * def_soldiers_modified * def_soldiers_multiplier), int((def_soldiers_modified + 1) * def_soldiers_multiplier), size=size)
	dftr = np.random.randint(int(0.4 * def_tanks_modified * 40), int((def_tanks_modified + 1) * 40), size=size)

	att_army_value = atsr + attr
	def_army_value = dfsr + dftr

	win_outcomes=np.greater(att_army_value,def_army_value)
	wins= np.unique(np.sum(win_outcomes,axis=1),return_counts=True)
	wins = {wins[0][i]:round(wins[1][i]/size[0]*100,2) for i in range(len(wins[0]))}
	
	await ctx.send(f"""**Simulating {att_soldiers:,} soldiers and {att_tanks:,} tanks vs {def_soldiers:,} soldiers and {def_tanks:,} tanks:**
```Immense triumph: {wins.get(3,0)}%\nModerate Victory: {wins.get(2,0)}%\nPyrrhic Victory: {wins.get(1,0)}%\nUtter Failure: {wins.get(0,0)}%```
**Casualties:**
```Attacker:\n\t-{ats_causalities:,} soldiers\n\t-{att_causalities:,} tanks \n\nDefender:\n\t-{dfs_causalities:,} soldiers\n\t-{dft_causalities:,} tanks```""")
	
@client.hybrid_command(name='air',with_app_command=True,description='Simulate a air attack')
async def air(ctx: commands.Context,att_aircraft:int,def_aircraft:int,options=None,max_num=1000000):
	
	att_roll = 0.7 * att_aircraft*3
	def_roll = 0.7 * def_aircraft*3
	def_troops_casualties = None
	logging.info(options)
	att_casualties,def_casualties=0,0
	wins = simulate_war(att_aircraft,def_aircraft,3)
	if options == None:
		att_casualties = def_roll*0.01*3
		def_casualties = att_roll*0.018337*3
	else:	
		options = options.strip('-')
		options = options.split(' ')
		if "soldiers" in options:
			att_casualties = def_roll*0.015385*3
			def_casualties = att_roll*0.009091*3
			max_causalities = max(min(max_num,max_num*0.75+1000,(att_roll-def_roll*0.5)*35*0.95),0)
			def_troops_casualties = (max_causalities*wins[3]+max_causalities*wins[2]*0.7+max_causalities*wins[3]*0.4)/100
		
		elif "tanks" in options:
			att_casualties = def_roll*0.015385*3
			def_casualties = att_roll*0.009091*3
			max_causalities = max(min(max_num,max_num*0.75+10,(att_roll-def_roll*0.5)*1.25*0.95),0)
			def_troops_casualties = (max_causalities*wins[3]+max_causalities*wins[2]*0.7+max_causalities*wins[3]*0.4)/100
		
		elif "ships" in options:
			att_casualties = def_roll*0.015385*3
			def_casualties = att_roll*0.009091*3
			max_causalities = max(min(max_num,max_num*0.75+4,(att_roll-def_roll*0.5)*0.0285 *0.95),0)
			def_troops_casualties = (max_causalities*wins[3]+max_causalities*wins[2]*0.7+max_causalities*wins[3]*0.4)/100

		if "b" in options:
			def_casualties = def_casualties*1.1
	
		if "f" in options:
			att_casualties = att_casualties*1.25
		

	
	
	result = f"""**Simulating {att_aircraft:,} planes vs {def_aircraft:,} planes:**
```Immense triumph: {wins[3]}%\nModerate Victory: {wins[2]}%\nPyrrhic Victory: {wins[1]}%\nUtter Failure: {wins[0]}%```
**Casualties:** 
```Attacker:\n\t-{att_casualties:,.2f} planes\n\nDefender:\n\t-{def_casualties:,.2f} planes"""
	if options not in [None,'-b','-f']:
		result = f"{result}\n\t-{def_troops_casualties:,.2f} {options[0]}```"
	else:
		result =f"{result}```"	
	await ctx.send(result)

@air.autocomplete('options')
async def air_autocomplete(interaction:discord.Interaction,current_val:str) -> typing.List[discord.app_commands.Choice[str]]:
	options = ['-soldiers ','-tanks ','-ships ','-b ','-f ']
	if current_val.lower() not in options:
		return [
			discord.app_commands.Choice(name=option, value=option)
			for option in options if current_val.lower() in option.lower()
		]
	else:
		options.remove(current_val)
		return [
			discord.app_commands.Choice(name=option, value=option)
			for option in options if current_val.lower() in option.lower()
		]

@client.hybrid_command(name='naval',with_app_command=True,description='Simulate a naval battle')
async def naval(ctx: commands.Context,att_ships:int,def_ships:int,*,modifiers:typing.Optional[typing.Literal['-b','-f']]):
	att_casualties,def_casualties = simulate_casualities(att_ships,def_ships,4)
	wins = simulate_war(att_ships,def_ships,4)
	if modifiers != None:
		modifiers = modifiers.split(' ')
		if "-b" in modifiers:
			def_casualties = def_casualties*1.1
		
		if "-f" in modifiers:
			att_casualties = att_casualties*1.25

	await ctx.send(f"""**Simulating {att_ships:,} ships vs {def_ships:,} ships:**
```Immense triumph: {wins[3]}%\nModerate Victory: {wins[2]}%\nPyrrhic Victory: {wins[1]}%\nUtter Failure: {wins[0]}%```
**Casualties:**
```Attacker:\n\t{att_casualties:,.2f} ships\n\nDefender:\n\t{def_casualties:,.2f} ships```""")			

@client.hybrid_command(name='pricehistory',with_app_command=True,description='Price history of the resource')
async def pricehistory(ctx:commands.Context,resource:str,days:int):
	query=f"{{tradeprices(first:{days}){{data{{date {resource}}}}}}}"
	async with httpx.AsyncClient() as client:
		fetchdata=await client.post(graphql_link,json={'query':query})
		fetchdata=fetchdata.json()['data']['tradeprices']['data']
		fetchdata.reverse()
		date=[datetime.strptime(x['date'],'%Y-%m-%d') for x in fetchdata]
		price=[x[f'{resource}'] for x in fetchdata]
        
		plt.figure(figsize=(8,7))
		plt.plot(date,price)
		plt.title(f'Price history of {resource}')
		plt.xticks(rotation=45)
		plt.savefig("test.png")
		plt.close()
		image = discord.File("test.png")
		await ctx.send(file=image)

@client.hybrid_command(name='fastbeige',with_app_command=True,description='Fastest attack pattern to reach beige')
async def fastbeige(ctx:commands.Context,resistance:commands.Range[int, 1,100],*,params:typing.Optional[str]):
	text = await beige_calculator(params,resistance,reverse=False)
	await ctx.send(f"```js\n{text}```")

@client.hybrid_command(name='slowbeige',with_app_command=True,description='Slowest attack pattern to reach beige')
async def slowbeige(ctx:commands.Context,resistance:commands.Range[int, 1,100],*,params:typing.Optional[str]):		
	text = await beige_calculator(params,resistance,reverse=True)
	await ctx.send(f"```js\n{text}```")

@client.hybrid_command(name='spyopval',with_app_command=True,description='Amount that can be looted from the target')
async def spyopval(ctx:commands.Context, *,message:str):
	x=re.match("You successfully gathered intelligence about [\w $'-.]+[\w $'-.]*. Your spies discovered that [\w $'-.]+ has [\w $'-.]{26,}. Your agents were [\w '-]{26,}. The operation cost you [$,.0-9]{2,} and [0-9]+ of your spies were captured and executed.",message)

	if bool(x):
		full_stop=message.find('.')
		nation=(message)[45:full_stop]
		logging.info(nation)
		nation_data = await nation_data_converter.get_unregistered('nation_id,war_policy',nation,'nation')
		nation_id =nation_data[0]
		if nation_id!=None and (message.count(nation)==2 or message.count(nation)==3):
			find_stuffs_orig = ['food', 'coal', 'oil', 'uranium', 'lead', 'iron', 'bauxite', 'gasoline', 'munitions', 'steel', 'aluminum']
			actual_loot,prices = await loot_from_text(message,2)    
			text=', '.join(actual_loot)
			conflict_text=', '.join(f"{find_stuffs_orig[x]}={actual_loot[x+1]}" for x in range(len(find_stuffs_orig)))
			now_time = str(datetime.now().replace(microsecond=0)).replace(' ','T')
			async with aiosqlite.connect('pnw.db') as db:
				await db.execute(f"insert into loot_data values (0,{nation_id},{text},'{now_time}') on conflict (nation_id) do update set war_id=0,money={actual_loot[0]},{conflict_text},war_end_date='{now_time}'")
				await db.commit()
			policy_modifier = 1
			if nation_data[1] ==5:
				policy_modifier = 1.4
			actual_loot=[str(int(0.14*float(x)/policy_modifier)) for x in actual_loot]
			loot_worth=int(actual_loot[0])
			for x in range(0,len(prices)):
				loot_worth= loot_worth+(int(actual_loot[x+1])*prices[x])
			await ctx.send(f'You can loot worth **${loot_worth:,}** assuming raid war type and pirate war policy.')
	else:
		await ctx.send("Please copy the result completely and run the command again.")		

@client.hybrid_command(name='banklootval',with_app_command=True,description='Estimated bank resources based on the beige')
async def banklootval(ctx:commands.Context,*,message:str):
	x = re.match("[\w $'-.]+[\w $'-.]* looted [0-9 .]{4,}% of [\w $'-.]+[\w $'-.]*'s alliance bank, taking: [\w $'-.]{26,}",message)
    
	if bool(x):
		actual_loot,prices = await loot_from_text(message,1) 
		percentage = re.findall('[0-9 .]{4,}%',message)[0][:-1]
		total_loot = [(int(loot)*100/float(percentage)) for loot in actual_loot]
		beige_worth = int(actual_loot[0])
		for x in range(0,len(prices)):
			beige_worth= beige_worth+(int(actual_loot[x+1])*prices[x])
		bank_worth = total_loot[0]
		for x in range(0,len(prices)):
			bank_worth= bank_worth+(int(total_loot[x+1])*prices[x])	
		await ctx.send(f'The beige was worth **${beige_worth:,}**. As {percentage}% of the bank was looted, the total estimated bank value is **${bank_worth:,}**')	
	else:
		await ctx.send("Please copy the result completely and run the command again.")	

@client.hybrid_command(name='lootval',with_app_command=True,description='Beige worth based on beige text provided')
async def lootval(ctx:commands.Context,*,message:str):
	x = re.match("[\w $'-.]+[\w $'-.]* crushed [\w $'-.]+[\w $'-.]*'s resistance to 0, resulting in their immediate surrender. [\w $'-.]+[\w $'-.]* looted [\w $'-.]{26,}",message)
	y = re.match("You have defeated your opponent by decreasing their Resistance to 0! You looted [\w $'-.]{26,}",message)
	if bool(x) or bool(y):
		actual_loot,prices = await loot_from_text(message,1) 
		beige_worth = float(actual_loot[0])
		for x in range(0,len(prices)):
			beige_worth= beige_worth+(float(actual_loot[x+1])*prices[x])
		await ctx.send(f'The beige was worth **${beige_worth:,}**.')	
	else:
		await ctx.send("Please copy the result completely and run the command again.")
	
@client.hybrid_command(name="war",with_app_command=True,description="Finds the highest infra targets")
async def war(ctx:commands.Context, *,flags:RaidFlags):
	score= await nation_data_converter.get('score',ctx.author.id)
	if score!=None:
		if ctx. interaction:
			await ctx.interaction.response.defer(thinking='Calculating')
		war_range = score*0.75,score*2.5
		page_query =f"""{{nations(min_score:{war_range[0]},max_score:{war_range[1]},vmode:false,first:500){{
		paginatorInfo{{
			lastPage
			total
		}}
			data{{
		id
		nation_name
		alliance_id
		alliance{{
			name
		}}
		num_cities
		cities{{
			infrastructure
		}}    
		soldiers
		tanks
		aircraft
		ships
		}}
		}} }}"""
		results=[]
		async with httpx.AsyncClient() as client:
			fetchdata = await client.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':page_query})
			fetchdata =fetchdata.json()['data']['nations']
			results.extend(fetchdata['data'])
			page_size = fetchdata['paginatorInfo']['lastPage']
			if page_size>1:
				for x in range(2,page_size+1):
					query =f"""{{nations(min_score:{war_range[0]},max_score:{war_range[1]},vmode:false,page:{x},first:500){{
							data{{
							id
							nation_name
							alliance_id
							alliance{{
							name
							}}
							num_cities
							cities{{
							infrastructure
							}}
							soldiers
							tanks
							aircraft
							ships
						}}
							}} }}"""
					fetchdata = await client.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':query})
					results.extend(fetchdata.json()['data']['nations']['data'])
		sheets_data = []
		for nations in results:
			nation_link = f'=HYPERLINK("https://politicsandwar.com/nation/id={nations["id"]}","{nations["nation_name"]}")'
			if nations['alliance_id']!='0':
				alliance_link = f'=HYPERLINK("https://politicsandwar.com/nation/id={nations["alliance_id"]}","{nations["alliance"]["name"]}")'
			else:
				alliance_link = 'None'
			infra = [city['infrastructure'] for city in nations['cities']]    
			avg_infra = sum(infra)/len(infra)
			max_infra = max(infra)
			sheets_data.append([nation_link,alliance_link,nations['num_cities'],max_infra,avg_infra,nations['soldiers'],nations['tanks'],nations['aircraft'],nations['ships']])
		sheets_data.sort(key=lambda x:x[3],reverse=True)
		sheets_data.insert(0,['Nation','Alliance','Cities','Max Infra','Average Infra','Soldiers','Tanks','Aircrafts','Ships'])    
		sheetID=sheets.create('War Targets',[{"properties":{"sheetId":0,'title':'Targets'}}])
		sheets.write_ranges(sheetID,f'Targets!A1:I{len(sheets_data)}',sheets_data)
		if ctx.interaction:
			await ctx.interaction.followup.send(f'https://docs.google.com/spreadsheets/d/{sheetID}')
		else:
			await ctx.send(f"https://docs.google.com/spreadsheets/d/{sheetID}")	
	else:
		emb = discord.Embed()
		emb.title='Register'
		emb.description='Usage : `;register <nation id|nation link>`'
		await ctx.send(content="You must be registered to use this command",embed=emb)

@commands.is_owner()
@client.command()
async def create_view(ctx:commands.Context,*,roles):
	roles = roles.split(' ')
	guild = ctx.guild
	print(roles)
	role_objects = [guild.get_role(int(role[3:-1])) for role in roles]
	view = MyPersistentView(role_objects)
	message = await ctx.send(view=view)
	roles = ','.join([role[3:-1] for role in roles])
	async with aiosqlite.connect('pnw.db') as db:
		await db.execute(f"insert into persistent_views values (?,?,?)",(guild.id,roles,message.id))
		await db.commit()

@client.command()
async def best_manu(ctx:commands.Context):
	emb = discord.Embed()
	emb.title = 'Best Manu'
	emb.description = f"Why your lazy ass can't find the best manu yourself"	
	emb.color = discord.Color.blue()
	view = ManuPersistentView()
	message = await ctx.send(embed=emb,view=view)
	async with aiosqlite.connect('pnw.db') as db:
		await db.execute(f"insert into persistent_views values ({ctx.guild.id},'',{message.id})")
		await db.commit()

@commands.is_owner()
@client.command()
async def leave(ctx,guild_id):
	guild = await client.fetch_guild(guild_id)
	await ctx.send(f"{guild} found")
	await guild.leave()
	await ctx.send(f"Left the guild {guild.name}")

@commands.is_owner()
@client.command()
async def sync_slash(ctx):
	await client.tree.sync()
	await ctx.send('slash commands updated')

@client.command()
@commands.has_any_role(1367769251443642488,1373425328587931700,1374933029394317453,454648130290319382)
async def force_register(ctx,user:discord.User,link):
	if link.startswith('http'):
		nation_id=int(link[37:])
	else:
		nation_id=link
	await update_registered_nations(user.id,user.name,nation_id)
	await ctx.send("Successfully registered")

@client.command()
async def ping(ctx):
	await ctx.send(f"Latency: {round(client.latency*1000)}ms")

@client.hybrid_command(name='range',description='Steps you need to take to be in range of the target nation',with_app_command=True)
async def range_command(ctx,target,user_nation='Default'):
	if user_nation == 'Default':
		user_nation = await nation_data_converter.get('registered_nations.nation_id',ctx.author.id)
	else:
		user_nation = await nation_data_converter.nation_id_finder(ctx,user_nation)	
	
	target = await nation_data_converter.nation_id_finder(ctx,target)

	user_nation_stats = await nation_data_converter.get_unregistered('score,cities,nukes,missiles,ships,tanks,aircraft',user_nation,return_row=True)
	user_nation_range = [user_nation_stats["score"]*0.75,user_nation_stats["score"]*2.75]
	
	score_val = {"nukes":15,"missiles":5,"tanks":0.025,"aircraft":0.3,"ships":1}
	
	target_nation = await nation_data_converter.get_unregistered('score,nation',target,return_row=True)
	result = f"To get in range to hit [{target_nation['nation']}](<https://politicsandwar.com/nation/id={target}>):\n"
	if target_nation["score"]>=user_nation_range[0] and target_nation["score"]<=user_nation_range[1]:
		await ctx.send("You are already in range")

	elif target_nation["score"]<user_nation_range[0]:
		
		reduce_score = user_nation_stats["score"]-(target_nation["score"]/0.75)
		keys = user_nation_stats.keys()
		keys.remove('score')
		keys.remove('cities')	
		i=0
		print(reduce_score)
		while reduce_score>0 and i<len(keys):
			if user_nation_stats[keys[i]]!=0:
				no_of_unit = reduce_score/score_val[keys[i]]
				if no_of_unit<=user_nation_stats[keys[i]]:
					reduce_score -= ceil(no_of_unit) * score_val[keys[i]]
					result = f"{result}Destroy {ceil(no_of_unit)} {keys[i].capitalize()}\n"
				else:
					reduce_score -= user_nation_stats[keys[i]] *score_val[keys[i]]	
					result = f"{result}Decom {user_nation_stats[keys[i]]} {keys[i].capitalize()}\n"
				
			i+=1		
		print(result)			
		if reduce_score>0:
			result = f"{result}Decom {round(reduce_score*40,2)} Infrastructure"
		await ctx.send(result)	
	else:
		
		increase_score = (target_nation["score"]/2.75)-user_nation_stats["score"]
		keys = ["aircraft","tanks","ships"]
		max_mili ={"tanks":1250,"aircraft":75,"ships":15}
		while increase_score>0 and i<len(keys):
			max_units = user_nation_stats["cities"]*max_mili[keys[i]]
			if user_nation_stats[keys[i]]<max_units:
				buy_units = increase_score/score_val[keys[i]]
				if buy_units<=max_units-user_nation_stats[keys[i]]:
					increase_score -= ceil(buy_units)*score_val[keys[i]]
					result = f"{result}Build {ceil(buy_units)} {keys[i].capitalize()}\n"
				else:
					increase_score -= (max_units-user_nation_stats[keys[i]]) *score_val[keys[i]]	
					result = f"{result}Build {max_units-user_nation_stats[keys[i]]} {keys[i].capitalize()}\n"	
		if increase_score>0:
			result = f"{result}Buy {round(reduce_score*40,2)} Infrastructure which is not recommended."
		await ctx.send(result)
		
@client.hybrid_command(name="spies",description="Calculates the odds for a spy attack",with_app_command=True)
async def spies(ctx,att_spies:int,def_spies:int,level=3,filter=None):
	odds = level * 25 + (att_spies*100/((def_spies*3)+1))
	filter_odd = 1
	filter_odds = {"tactician":1.15,"arcane":0.85,"covert":1.15}
	type_odds = {"intel":[1,":brain:"],"soldiers":[1,":military_helmet:"],"spies":[1.5,":detective:"],"tanks":[1.5,":articulated_lorry:"],"aircraft":[2,":airplane:"],"ships":[3,":ship:"],"missiles":[4,":rocket:"],"nukes":[5,":radioactive:"]}
	if filter!=None:	
		filter_odd = filter_odds[filter] 	
	all_odds = {k:[min((odds/v[0])*filter_odd,99),v[1]] for k,v in type_odds.items()}
	result =""
	for spy_type,value in all_odds.items():
		result = f"{result}{value[1]} {spy_type.capitalize()}: Success chance {round(value[0],2)}%, Caught chance {round(100-value[0]/102 *100,2)}%\n"
	await ctx.send(result)	

@client.hybrid_command(name="tiering",description="Gives a tiering chart of the target coalitions",with_app_command=True)
async def tiering(ctx,coalition_1,coalition_2,filters=None):
	query = f"""{{alliances(id:[{coalition_1},{coalition_2}],first:500){{
				data{{
					id
					nations{"(vmode:false)" if filters!='-vm' else ""}{{
						num_cities,alliance_position,last_active
						}}
					}}
				}} }}"""
	async with httpx.AsyncClient() as client:
		fetchdata = await client.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':query})
		fetchdata = fetchdata.json()['data']['alliances']['data']
	coalition_1_ids = coalition_1.split(',')	
	coalition_1_nation_list,coalition_2_nation_list = [],[]
	
	def classify_nations(alliance, tier_list):
		now_datetime = datetime.now(timezone.utc)
		timediff = timedelta(days=7)
		for nation in alliance['nations']:
			if nation["alliance_position"] != "APPLICANT" and (filter!="-excludeinactive" or  now_datetime-datetime.strptime(nation["last_active"],"%Y-%m-%d %H:%M:%S")<timediff):
				tier_list.append(nation["num_cities"])

	for alliance in fetchdata:
		if alliance['id'] in coalition_1_ids:
			classify_nations(alliance, coalition_1_nation_list)
		else:
			classify_nations(alliance, coalition_2_nation_list)


	def count_cities(city_list):
		city_counts = {}
		for cities in city_list:
			if cities not in city_counts:
				city_counts[cities] = 0
			city_counts[cities] += 1
		return city_counts

	coalition_1_tiers = count_cities(coalition_1_nation_list)
	coalition_2_tiers = count_cities(coalition_2_nation_list)		
	sheetID=sheets.create('Tier Chart',[{"properties":{"sheetId":0,'title':'Tiers'}}])
	all_city_values = sorted(set(coalition_1_tiers.keys()) | set(coalition_2_tiers.keys()))

	# Build values for sheet
	values = [["City", "Coalition 1", "Coalition 2"]]
	for city in all_city_values:
		values.append([
			city,
			coalition_1_tiers.get(city, 0),
			coalition_2_tiers.get(city, 0)
		])

	# Add total row
	values.append([
		"Total",
		len(coalition_1_nation_list),
		len(coalition_2_nation_list)
	])
	rules_dict_list = [{"startColumnIndex": 1,"endColumnIndex": 2,"userEnteredValue":"=GT(B2,C2)","backgroundColor":{"green":1}},
	{"startColumnIndex": 1,"endColumnIndex": 2,"userEnteredValue":"=LTE(B2,C2)","backgroundColor":{"red":1}},
	{"startColumnIndex": 2,"endColumnIndex": 3,"userEnteredValue":"=GT(C2,B2)","backgroundColor":{"green":1}},
	{"startColumnIndex": 2,"endColumnIndex": 3,"userEnteredValue":"=LTE(C2,B2)","backgroundColor":{"red":1}}]
	sheets.write_ranges(sheetID, f'Tiers!A1:C{len(values)}', values)
	
	rules=[]
	for rules_dict in rules_dict_list:
			rule={
			"addConditionalFormatRule": {
					"rule": {
						"ranges": [
							{
								"sheetId": 0,  
								"startRowIndex": 1,
								"endRowIndex": len(values), 
								"startColumnIndex": rules_dict["startColumnIndex"],
								"endColumnIndex": rules_dict["endColumnIndex"]
							}
						],
						"booleanRule": {
							"condition": {
								"type": "CUSTOM_FORMULA",
								"values": [
									{
										"userEnteredValue": rules_dict['userEnteredValue']
									}
								]
							},
							"format": {
								"backgroundColor": rules_dict['backgroundColor']
							}
						}
					},
					"index": 0
				}
			}
			rules.append(rule)	
	sheets.conditional_formatting(sheetID,rules)
	await ctx.send(f'https://docs.google.com/spreadsheets/d/{sheetID}')

@client.hybrid_command(name='aamil',description="Returns the current military info of the given alliances",with_app_command=True)
async def aamil(ctx,alliance_ids):
	fetchdata = await aa_stalker(alliance_ids)
	sheetID=sheets.create('Milcom Sheet',[{"properties":{"sheetId":0,'title':'Milcom'}}])
	values = [('Nation','Alliance','Cities','Score','War Policy','Last Actvie','Beige','Off Wars','Def Wars','Soldiers','Tanks','Planes','Ships','Missiles','Nukes','Spies','Spy Sat','Spy Slot')]
	
	for alliance in fetchdata:
		for nation in alliance['nations']:
			values.append((f'=HYPERLINK("https://politicsandwar.com/nation/id={nation["id"]}","{nation["nation_name"]}")',alliance["name"],nation["num_cities"],
				nation['score'],nation['war_policy'],nation_data_converter.time_converter(datetime.strptime(nation["last_active"].split('+')[0],"%Y-%m-%dT%H:%M:%S")),
				'Yes' if nation['beige_turns']>0 else 'No',nation['offensive_wars_count'],nation['defensive_wars_count'],nation['soldiers'],nation['tanks'],nation['aircraft'],
				nation['ships'],nation['missiles'],nation['nukes'],nation['spies'],'Yes' if nation['spy_satellite'] else 'No', 'Yes' if nation['espionage_available'] else 'No'))
	sheets.write_ranges(sheetID,f'Milcom!A1:R{len(values)+1}',values)
	await ctx.send(f'https://docs.google.com/spreadsheets/d/{sheetID}')

async def aa_stalker(alliance_ids,filters={'include_vm':False}):
	vmode = filters['include_vm']
	query = f"""{{alliances(id:[{alliance_ids}],first:500){{
			data{{
				name
				nations(vmode:{str(vmode).lower()}){{
					id,nation_name,num_cities,score,war_policy,last_active,defensive_wars_count,beige_turns,offensive_wars_count
					soldiers,tanks,aircraft,ships,missiles,nukes,spies,spy_satellite,espionage_available,alliance_position
					}}
				}}
			}} }}"""
	async with httpx.AsyncClient() as client:
		fetchdata = await client.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':query})
		fetchdata = fetchdata.json()['data']['alliances']['data']
	return fetchdata

@client.hybrid_command(name='stopdailyalerts',description="Stops alert dms",with_app_command=True)
async def stopdailyalerts(ctx,nation_id,value):
	async with aiosqlite.connect('pnw.db') as db:
		if int(value):
			data_to_be_inserted=("insert or ignore into stop_dms values(%s,%s)") % (nation_id,1)
			await ctx.send('Alerts disabled')
		else:
			data_to_be_inserted = ("delete from stop_dms where nation_id=%s") % (nation_id)
			await ctx.send('Alerts enabled')
		await db.execute(data_to_be_inserted)
		await db.commit()	

@client.hybrid_command(name='productionefficiency',description="Gives the profitablilty of producing each resource",with_app_command=True)
async def production_efficiency(ctx):
	production_per_day = {"munitions":{"production":21.6,"usage":["lead",6],"op_cost":3500},
					   "gasoline":{"production":12,"usage":["oil",6],"op_cost":4000},
					   "aluminum":{"production":12.24,"usage":["bauxite",4.08],"op_cost":2500},
					   "steel":{"production":12.24,"usage":["iron","coal",4.08],"op_cost":4000}}
	raw_op_cost = {"coal":400,"oil":600,"uranium":5000,"iron":1600,"lead":1500,"bauxite":1600}
	async with aiosqlite.connect('pnw.db') as db:
		db.row_factory =aiosqlite.Row
		prices = await get_prices(db)
		prices = dict(prices)
	prices.pop('food')
	profitability = []
	for rss in prices.keys():
		if rss not in production_per_day.keys():
			if not rss == 'uranium':
				profitability.append([rss.capitalize(),3*10*1.5*prices[rss]-10*raw_op_cost[rss]])
			else:
				profitability.append([rss.capitalize(), 12*5*1.5*prices[rss]-5*raw_op_cost[rss]])
		else:
			production_info = production_per_day[rss]
			if not rss == 'steel':
				profitability.append([rss.capitalize() ,production_info["production"]*5*1.5*prices[rss]-production_info["usage"][1]*prices[production_info["usage"][0]]-production_info["op_cost"]*5])
			else:
				profitability.append([rss.capitalize(), production_info["production"]*5*1.5*prices[rss]-production_info["usage"][2]*prices[production_info["usage"][0]]-production_info["usage"][2]*prices[production_info["usage"][1]]-production_info["op_cost"]*5])
	profitability.sort(key=lambda x: x[1], reverse=True)
	profit_text = "\n".join([f" {i[0]:<9}\t\t{round(i[1],2):,}" for i in profitability])
	profit_text = f'```js\nResource \t Profit Per Day🤑🤑🤑 \n{profit_text}```'		
	await ctx.send(profit_text)

if __name__=='__main__':
	web_flask.run()
	client.run(os.getenv('DISCORD_TOKEN'))		