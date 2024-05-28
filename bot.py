import os,discord,sqlite3,logging,requests,time,re
from discord.ext import commands
from commands.scripts import nation_data_converter,updater#,sheets
from datetime import datetime,timedelta
import DiscordUtils
import aiosqlite,asyncio,httpx

logging.basicConfig(level=logging.INFO)
aiosqlite.threadsafety=1

def update_registered_nations(author_id,author_name,nation_id):
	connection=sqlite3.connect('politics and war.db')
	data_to_be_inserted=("insert into registered_nations values(%s,'%s',%s) on conflict(discord_id) do update set user_name='%s',nation_id=%s") % (author_id,author_name,nation_id,author_name,nation_id)
	connection.execute(data_to_be_inserted)
	connection.commit()
	connection.close()	
pass

def get(search_element,_id,search_using='discord_id'):
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	search="select %s from all_nations_data inner join registered_nations on registered_nations.nation_id =all_nations_data.nation_id where %s='%s'" % (search_element,search_using,_id)
	cursor.execute(search)
	score=cursor.fetchone()
	cursor.close()
	connection.close()
	if score !=None and len(score)==1:
		score=score[0]
	return score
pass

def get_unregistered(search_element,_id,search_using='nation_id',fetchall=False):
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	search=f"select {search_element} from all_nations_data where {search_using}='{_id}'"
	cursor.execute(search)
	if fetchall==False:
		score=cursor.fetchone()
	else:
		score=cursor.fetchall()
	cursor.close()
	connection.close()
	if score !=None and len(score)==1:
		score=score[0]
		if type(score)==(list or tuple) and len(score)==1:
			score=score[0]	
	return score
pass

async def nation_id_finder(ctx,id_or_name):
	try:
		discord_id= await commands.converter.MemberConverter().convert(ctx,id_or_name)
		nation_id=get('registered_nations.nation_id',discord_id.id)
	except commands.BadArgument:
		if id_or_name.isdigit():
				nation_id=int(id_or_name)
		elif id_or_name.startswith('https://politicsandwar.com/nation'):
			nation_id=int(id_or_name[-6:])	
		else:
			finder=['nation','leader']
			x=0
			nation_id=id_or_name
			while (isinstance(nation_id,str) or nation_id==None) and x<2:
				nation_id=get_unregistered('nation_id',id_or_name,finder[x])
				x+=1			
	return nation_id	
pass

def aa_finder(id_or_name):
	if id_or_name.isdigit()	:
		alliance_id=id_or_name
	elif id_or_name.startswith('http'):
		alliance_id=id_or_name[39:]
	else:
		alliance_id=get_unregistered('alliance_id',id_or_name,'alliance')
	return alliance_id
pass		

async def targets(war_range,inactivity_time,aa,beige,beige_turns):
	async with aiosqlite.connect('politics and war.db') as db:
		date=datetime.now().replace(microsecond=0)
		date = date -timedelta(days=inactivity_time)
		search_list1 = ','.join([f'loot_data.{x}' for x in ['nation_id', 'money', 'food', 'coal', 'oil', 'uranium', 'lead', 'iron', 'bauxite', 'gasoline', 'munitions', 'steel', 'aluminum']])
		search_list2 = ','.join([f'all_nations_data.{x}' for x in ['alliance','beige_turns','soldiers', 'tanks', 'aircraft', 'ships']])
		targets_list = f"select {search_list1},{search_list2} from loot_data inner join all_nations_data on loot_data.nation_id =all_nations_data.nation_id where score>{war_range[0]} and score<{war_range[1]} {beige} and vmode=0 and defensive_wars<>3 {aa} {beige_turns} and date(last_active)<'{date}'"
		print(targets_list)
		cursor = await db.execute(targets_list)
		print([x[0] for x in cursor.description])
		all_targets= await cursor.fetchall()
		prices=await get_prices(db)
		final_list=[]
		for y in range(0,len(all_targets)):
			amount=all_targets[y][1]
			for x in range(0,11):
				amount=amount+(all_targets[y][x+2]*prices[x])
			data_list=[all_targets[y][0],amount,all_targets[y][13],all_targets[y][14],all_targets[y][15],all_targets[y][16],all_targets[y][17],all_targets[y][18]]
			final_list.insert(y,data_list)	
		await cursor.close()
	final_list.sort(key=lambda x:x[1],reverse=True)
	final_list=final_list[:9]
	print(final_list)
	for data in final_list:
		dep_date=await last_bank_rec(data[0])
		data.append(dep_date)
	print(final_list)
	return final_list
pass

async def last_bank_rec(nation_id):
	query=f"""{{
  	bankrecs(sid:{nation_id},orderBy:[{{column:DATE,order:DESC}}],first:1,rtype:2){{
    data{{date
	}}
  	}}
	}}"""
	async with httpx.AsyncClient() as client:
		fetchdata=await client.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':query})
		fetchdata=fetchdata.json()['data']['bankrecs']['data'][0]['date']
	return fetchdata.split('+')[0]

async def get_prices(db):
	cursor= await db.execute("select * from trade_prices")
	price= await cursor.fetchone()
	await cursor.close()
	return price	
pass

def inactive_players(alliance_id):
	all_nations_in_alliance='https://politicsandwar.com/api/nations/?key=10433a4b8a7dec&alliance_id='+str(alliance_id)
	fetchdata=requests.get(f"{all_nations_in_alliance}")
	fetchdata=fetchdata.json()
	d={"link":"","days":0,"hours":0,'position':''}
	y=0
	m=[]
	for x in range(0,len(fetchdata['nations']),1):
		minutessinceactive=fetchdata['nations'][x]['minutessinceactive']
		alliance_position=fetchdata['nations'][x]['allianceposition']
		if minutessinceactive>7200:
			nation_id=fetchdata['nations'][x]['nationid']
			d['link']='https://politicsandwar.com/nation/id='+ str(nation_id)
			d['days']=int(minutessinceactive/1440)
			d['hours']=int((minutessinceactive%1440)/60)
			if alliance_position==2:
				d['position']='Member'
			elif alliance_position==1:
				d['position']='Applicant'	
			m.append(y)
			m[y]=dict(d)
			y=y+1
	return m,y
pass

def aa_color_compare(alliance_id):
	query="""{
		alliances(id:%s,first:1){ 
			data{
				color
				nations{
					id
					color
					alliance_position
					vmode
				}
			}
		}
	}"""% (alliance_id)
	fetchdata=requests.post(f"{graphql_link}",json={'query':query})
	fetchdata=fetchdata.json()
	color_list=[]
	y=0
	for x in fetchdata['data']['alliances']['data'][0]['nations']:
		if x['alliance_position']!="APPLICANT" and x['color']!=fetchdata['data']['alliances']['data'][0]['color'] and x['vmode']==0:
			color_tuple=(x['id'],x['color'])
			color_list.insert(y,color_tuple)
			y+=1
	return color_list		
pass

def update_subscriptions(server_id,command_name,date_time):
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	days=date_time.find('d')
	hours=date_time.find('h')
	mins=date_time.find('m')
	if mins!=-1:
		mins=date_time[hours+1:mins]
	else:
	 	mins=0	
	if hours!=-1:
		hours=date_time[days+1:hours]
	else:
		hours=0	
	if days!=-1:
		days=date_time[:days]	
	else:
		days=0
	current_date=datetime.now().replace(microsecond=0)
	end_date=current_date+timedelta(days=int(days),hours=int(hours),minutes=int(mins))
	update_table="insert into subscriptions values(%s,'%s','%s') on conflict(server_id,command_name) do update set end_date='%s'" % (server_id,command_name,end_date,end_date)
	cursor.execute(update_table)
	connection.commit()
	cursor.close()
	connection.close()
pass

def check_subscriptions(server_id,command_name):
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	search_subs=("select * from subscriptions where server_id=%s and command_name='%s'") %(server_id,command_name)
	cursor.execute(search_subs)
	validity=cursor.fetchone()
	cursor.close()
	connection.close()	
	return validity
pass

def check_efficency(nation_id):	
	query="""{
		nations(id:%s,first:1){
			data{
				cities{
					id
					name
					infrastructure
					land
					coalpower
					oilpower
					windpower
					nuclearpower
					coalmine
					oilwell
					uramine
					leadmine
					ironmine
					bauxitemine
					farm
					gasrefinery
					aluminumrefinery
					munitionsfactory
					steelmill
					policestation
					hospital
					recyclingcenter
					subway
					supermarket
					bank
					mall
					stadium
					barracks
					factory
					airforcebase
					drydock
				}
			}
		}      
	}"""	% (nation_id)
	fetchdata=requests.get(graphql_link,json={'query':query})
	fetchdata=fetchdata.json()
	fetchdata=fetchdata['data']['nations']['data'][0]['cities']
	total_keys= [keys for keys in fetchdata[0]]
	total_keys.pop(0)
	total_keys.pop(0)
	total_values=[0 for x in total_keys]
	for y in range(0,len(fetchdata)): 
			temp=[fetchdata[y][keys] for keys in total_keys]
			total_values=[total_values[i]+temp[i] for i in range(0,len(temp))]
	avg_value=[round(i/len(fetchdata),2) for i in total_values]
	return avg_value,len(fetchdata)
pass

def check_for_defcon(nation_id):
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	data="select barracks,factory,hangar,drydock,all_nations_data.soldiers,all_nations_data.tanks,all_nations_data.aircraft,all_nations_data.ships from defcon inner join all_nations_data on all_nations_data.alliance_id = defcon.alliance_id where all_nations_data.nation_id=%s" % (nation_id)
	cursor.execute(data)
	defcon=cursor.fetchone()
	cursor.close()
	connection.close()
	return defcon
pass

def check_for_build(nation_id,infra):
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	data="select build_details from build inner join all_nations_data on all_nations_data.alliance_id = build.alliance_id where (all_nations_data.nation_id=%s and build.min_infra<=%s) order by build.min_infra desc limit 1 " % (nation_id,infra)
	cursor.execute(data)
	build=cursor.fetchone()
	cursor.close()
	connection.close()
	return build
pass

def get_wars(my_nation_id):
	query="""{
		wars(nation_id:%s,days_ago:5){
			id
			attid
			defid
			war_type
			groundcontrol
			airsuperiority
			navalblockade
			}
		}""" % (my_nation_id)
	fetchdata=requests.get(graphql_link,json={'query':query})
	fetchdata=fetchdata.json()
	fetchdata=fetchdata['data']['wars']
	print(fetchdata)
	return fetchdata
pass		

def logging_in_to_pnw():
	try:
		session=requests.session()
		login_url='https://test.politicsandwar.com/login/'
		login_data={'password':'3duq3NjyLQ7B@ir','email':'jaiswalayush833@gmail.com','loginform':'login'}
		login=session.post(f"{login_url}",login_data)
		print('logged in successfully')
		return session
	except:
		print('an error occured')	
pass

async def repeat_every_n_seconds(func_name,interval):
	func=getattr(updater,func_name)
	while True:
		await func()
		await asyncio.sleep(interval)

graphql_link='https://api.politicsandwar.com/graphql?api_key=10433a4b8a7dec'
intents = discord.Intents.default()	
intents.message_content = True
client=commands.AutoShardedBot(command_prefix=';',help_command=None,intents=intents)
game = discord.Game("I am noob")

@client.event
async def on_ready():
	print('Bot is ready')
	await client.change_presence(status=discord.Status.online, activity=game)

@client.listen('on_message')
async def spy_reports(message):
	x=re.match("You successfully gathered intelligence about [A-Za-z]+[A-z a-z]*. Your spies discovered that [A-Za-z]+[A-z a-z]* has [0-9]+ spies, [$.,0-9]{2,}, [,.0-9]+ coal, [,.0-9]+ oil, [,.0-9]+ uranium, [,.0-9]+ lead, [,.0-9]+ iron, [,.0-9]+ bauxite, [,.0-9]+ gasoline, [,.0-9]+ munitions, [,.0-9]+ steel, [,.0-9]+ aluminum, and [,.0-9]+ food. Your agents were [\w '-]{26,}. The operation cost you [$,.0-9]{2,} and [0-9]+ of your spies were captured and executed.",message.content)
	if bool(x):
		full_stop=message.content.find('.')
		nation=(message.content)[45:full_stop]
		nation_id=get_unregistered('nation_id',nation,'nation')
		if nation_id!=None and (message.content.count(nation)==2 or message.content.count(nation)==3):
			problem_part=message.content.find('Your agents were ')+17
			full_stop=message.content.find('.',problem_part+17,400)
			compare_text1='able to operate undetected'
			compare_text2=f"caught and identified by {nation}'s counter-intelligence forces"
			if (message.content)[problem_part:full_stop]==compare_text1 or (message.content)[problem_part:full_stop]==compare_text2:
				#connection=sqlite3.connect('politics and war.db')
				#cursor=connection.cursor()
				#loot_info=re.findall('[,.0-9]{3,}',message.content)
				#actual_loot=[loot_info[x].replace(',','') for x in range(0,len(loot_info)-1)]
				#actual_loot=[str(int(0.14*float(x))) for x in actual_loot]
				#text=', '.join(actual_loot)
				#prices=get_prices(cursor)
				#insert_data=f"insert into loot_data(defender_nation_id,money_looted,coal,oil,uranium,iron,bauxite,`lead`,gasoline,munitions,steel,aluminum,food,war_end_date) values ({nation_id},{text},'{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}') on conflict(defender_nation_id) do update set money_looted={actual_loot[0]},coal={actual_loot[1]},oil={actual_loot[2]},uranium={actual_loot[3]} ,iron={actual_loot[4]} ,bauxite={actual_loot[5]} ,`lead`={actual_loot[6]} ,gasoline={actual_loot[7]} ,munitions={actual_loot[8]} ,steel={actual_loot[9]} ,aluminum={actual_loot[10]} ,food={actual_loot[11]} ,war_end_date='{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}'"
				#cursor.execute(insert_data)
				#connection.commit()
				#cursor.close()
				#connection.close()
				loot_worth=int(actual_loot[0])
				for x in range(0,len(prices)):
					loot_worth= loot_worth+(int(actual_loot[x+1])*prices[x])
				await message.channel.send(f'You can loot worth ${"{:,}".format(loot_worth)}')

@commands.is_owner()
@client.command()
async def add_subscription(ctx,command_name,time):
	update_subscriptions(ctx.guild.id,command_name,time)
	await ctx.send('Subscriptions updated')	

@client.command()
async def audit(ctx,nation_id=None):
	if nation_id==None:
		nation_id=str(ctx.author.id)
	nation_id=await nation_id_finder(ctx,nation_id)
	results,city_count=check_efficency(nation_id)
	embed_name=['Infra','Land','Coalpower','Oilpower','Windpower','Nuclearpower','Coalmine','Oilwell','Uramine','Leadmine','Ironmine','Bauxitemine','Farm','Gasrefinery','Aluminumrefinery','Munitionsfactory','Steelmill','Policestation','Hospital','Recyclingcenter','Subway','Supermarket','Bank','Mall','Stadium','Barracks','Factory','Hangar','Drydock']
	embed1=discord.Embed()
	embed1.title='Build average details'
	for x in range(0,len(embed_name)):
		if results[x]!=0:
			embed1.add_field(name=embed_name[x],value=results[x],inline=True)
	defcon=check_for_defcon(nation_id)
	print(defcon)
	embed2=	discord.Embed()
	embed2.title='Defcon'
	text=''
	if defcon!=None:
		for x in range(0,4):
			value='✓'
			if results[x+25]<defcon[x]:
				value='✘'
			embed2.add_field(name=embed_name[x+25],value=value,inline=True)
	else:
		text="Defcon hasn't been set for your alliance"			
	build=(check_for_build(nation_id,results[0]))
	if build!=None:
		embed3=discord.Embed()
		embed3.title='Audit'
		build=build[0]
		build=eval(build)
		improvements=[build[keys] for keys in build]
		for x in range(0,23):
			requirements_met='❌'
			if results[x+2]>=improvements[x] and improvements[x]!=0:
				requirements_met='✅'
				embed3.add_field(name=embed_name[x+2],value=requirements_met)
			elif results[x+2]<improvements[x]:
				embed3.add_field(name=embed_name[x+2],value="Requirement not satisfied")	
	else:
		text1="Build hasn't been set for this infra"			
	embed4=discord.Embed()
	embed4.title='To do'
	emoji_list=['one','two','three','four','five','six','seven','eight','nine']	
		
	await ctx.send(embed=embed1)
	if defcon!=None:
		await ctx.send(embed=embed2)
	else:
		await ctx.send(text)
	if build!=None:
		await ctx.send(embed=embed3)
	else:
		await ctx.send(text1)	

@client.command()
async def check_color(ctx):
	alliance_id=get('alliance_id',ctx.author.id)
	data=aa_color_compare(alliance_id)
	embed=discord.Embed()
	embed.title='Color trade bloc'
	y=0
	while y<len(data) and y<25:
		embed.add_field(name=f'{y+1}.https://politicsandwar.com/nation/id={data[y][0]}',value=f'Color: {data[y][1]}')
		y=y+1
	await ctx.send(embed=embed)

@commands.is_owner()
@client.command()
async def guilds(ctx):
	guilds= await client.fetch_guilds().flatten()
	embed=discord.Embed()
	embed.title='Servers'
	embed.description='The list of the alliances the bot is present in:'
	counter=1
	for guild in client.guilds:
		embed.add_field(name=f'{counter}.{guild.name}',value=f'Server ID:{guild.id}',inline=False)
		counter=counter+1
	await ctx.send(embed=embed)	

@client.command()
async def inactivity(ctx):
	alliance_id=get('alliance_id',ctx.author.id)
	dictionary,counter=inactive_players(alliance_id)
	embed=discord.Embed()
	embed.title='Inactive players'
	y=0
	while y<counter and y<25:
		link=dictionary[y]['link']
		days=dictionary[y]['days']
		hours=dictionary[y]['hours']
		position=dictionary[y]['position']
		embed.add_field(name=f'{y+1}.{link}',value=f'Inactive for {days} days, {hours} hours\n Position:{position}')
		y=y+1
	await ctx.send(embed=embed)	

@client.command()
async def loot(ctx,*,nation_id):
	nation_id=await nation_id_finder(ctx,nation_id)
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	cursor.execute(f'select * from loot_data where nation_id={nation_id}')
	loot=cursor.fetchone()
	cursor.close()
	connection.close()
	print(loot)
	embed=discord.Embed()
	embed.title=f'Loot info for {get_unregistered("nation",nation_id)}'
	list_of_things_to_find=['Money','Coal','Oil','Uranium','Iron','Bauxite','Lead','Gasoline','Munitions','Steel','Aluminum','Food']
	for x in range(0,len(list_of_things_to_find)):
		embed.add_field(name=list_of_things_to_find[x],value=loot[x+3],inline=True)
	today_date=datetime.now()
	loss_date=datetime(int(loot[15][:4]),int(loot[15][5:7]),int(loot[15][8:10]),int(loot[15][11:13]),int(loot[15][14:16]),int(loot[15][17:19]))	
	difference=today_date-loss_date
	minutes,hours=0,0
	seconds=int(str(difference.seconds))
	if seconds>60:
		minutes=int(seconds/60)
		seconds=seconds-(minutes*60)
		if minutes>60:
			hours=int(minutes/60)
			minutes=minutes-hours*60
	add='war loss'
	print(loot[0])
	if loot[0]==None:
		add='spy op'		
	embed.set_footer(text=f'Based on {add} from {difference.days}d{hours}h{minutes}m{seconds}s ago')	
	await ctx.send(embed=embed)	

@client.command()
async def nation(ctx):
	nation_data=get('*',ctx.author.id)	
	if isinstance(nation_data,str):
		await ctx.send(f'Register to use this command')
	else:
		embed=discord.Embed()
		embed.title=f'{nation_data[1]}'
		embed.url=f'https://politicsandwar.com/nation/id={nation_data[0]}'	
		embed.add_field(name='Score',value=nation_data[13],inline=True)
		embed.add_field(name='Offensive War Range',value=f'{int(0.75*nation_data[13])}-{int(1.75*nation_data[13])}',inline=True)
		embed.add_field(name='Defensive War Range',value=f'{int(nation_data[13]/1.75)}-{int(nation_data[13]/0.75)}',inline=True)
		embed.add_field(name='Cities',value=nation_data[10],inline=True)
		embed.add_field(name='Color',value=nation_data_converter.color(nation_data[6]),inline=True)
		if nation_data[6]==0:
			embed.add_field(name='Beige Turns',value=f'{nation_data[16]} turns',inline=True)
		embed.add_field(name='Continent',value=nation_data_converter.continent(nation_data[3]),inline=True)
		embed.add_field(name='Alliance',value=f"[{nation_data[8]}](https://politicsandwar.com/alliance/id={nation_data[7]})",inline=True)
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



class RaidFlags(commands.FlagConverter):
	all_nations: bool = False
	inactivity_days: int = 0
	alliances: str = '0'
	beige: bool = True
	beige_turns: int = 216

@client.command()
async def raid(ctx, *,flags:RaidFlags):
	results=check_subscriptions(ctx.guild.id,'raid')
	print(flags.alliances)
	if results!=None:
		today_date=datetime.now().replace(microsecond=0)
		today_date_obj=time.strptime(str(today_date),"%Y-%m-%d %H:%M:%S")
		end_date=time.strptime(results[2],"%Y-%m-%d %H:%M:%S")
		if end_date>today_date_obj:
			score=get('score',ctx.author.id)
			page1=discord.Embed()
			if score!=None:
				flags.alliances=flags.alliances.split(',')
				print(flags.alliances)
				if flags.beige:
					flags.beige_turns=f'and beige_turns<{flags.beige_turns}'
				else:
					flags.beige_turns=''			
				flags.beige='' if flags.beige==True else 'and color<>0'
				if flags.alliances=='0' and flags.all_nations==False:
					flags.alliances='and alliance_id=0'	
				elif flags.all_nations==False:
					flags.alliances.append('0')
					flags.alliances=tuple(flags.alliances)
					flags.alliances=f'and alliance_id in {flags.alliances}'
				else:
					flags.alliances=''		
				war_range=score-score*25/100,score+score*75/100
				list_of_targets=await targets(war_range,flags.inactivity_days,flags.alliances,flags.beige,flags.beige_turns)
				page1.title='Targets'
				x=0
				while x<len(list_of_targets) and x<3:
					loot=(list_of_targets[x][1])
					loot='{:,}'.format(loot)
					loot='Loot:' + loot
					page1.add_field(name=f'{x+1}.https://politicsandwar.com/nation/id={(list_of_targets[x][0])}',value=f'{loot}',inline=False)
					page1.add_field(name='Alliance',value=list_of_targets[x][2],inline=True)
					if list_of_targets[x][3]!=0:
						page1.add_field(name='Beige',value=f'{list_of_targets[x][3]} turns',inline=True)	
					page1.add_field(name='Soldiers',value=list_of_targets[x][4],inline=True)
					page1.add_field(name='Tanks',value=list_of_targets[x][5],inline=True)
					page1.add_field(name='Aircrafts',value=list_of_targets[x][6],inline=True)
					page1.add_field(name='Ships',value=list_of_targets[x][7],inline=True)
					page1.add_field(name='Last bank deposit',value=today_date-datetime.strptime(list_of_targets[x][8],"%Y-%m-%dT%H:%M:%S"),inline=True)
					x=x+1
				pass	
				if len(list_of_targets)>x:
					page2=discord.Embed()
					embeds=[page1,page2]
					page2.title='Targets'	
					while x<len(list_of_targets) and x<6:
						loot=(list_of_targets[x][1])
						loot='{:,}'.format(loot)
						loot='Loot:' + loot
						page2.add_field(name=f'{x+1}.https://politicsandwar.com/nation/id={(list_of_targets[x][0])}',value=f'{loot}',inline=False)
						page2.add_field(name='Alliance',value=list_of_targets[x][2],inline=True)
						if list_of_targets[x][3]!=0:
							page2.add_field(name='Beige',value=f'{list_of_targets[x][3]} turns',inline=True)				
						page2.add_field(name='Soldiers',value=list_of_targets[x][4],inline=True)
						page2.add_field(name='Tanks',value=list_of_targets[x][5],inline=True)
						page2.add_field(name='Aircrafts',value=list_of_targets[x][6],inline=True)
						page2.add_field(name='Ships',value=list_of_targets[x][7],inline=True)
						page2.add_field(name='Last bank deposit',value=today_date-datetime.strptime(list_of_targets[x][8],"%Y-%m-%dT%H:%M:%S"),inline=True)		
						x=x+1
					if len(list_of_targets)>x:
						page3=discord.Embed()
						embeds=[page1,page2,page3]
						page3.title='Targets'
						while x<len(list_of_targets) and x<9:	
							loot=(list_of_targets[x][1])
							loot='{:,}'.format(loot)
							loot='Loot:' + loot
							page3.add_field(name=f'{x+1}.https://politicsandwar.com/nation/id={(list_of_targets[x][0])}',value=f'{loot}',inline=False)
							page3.add_field(name='Alliance',value=list_of_targets[x][2],inline=True)
							if list_of_targets[x][3]!=0:
								page3.add_field(name='Beige',value=f'{list_of_targets[x][3]} turns',inline=True)				
							page3.add_field(name='Soldiers',value=list_of_targets[x][4],inline=True)
							page3.add_field(name='Tanks',value=list_of_targets[x][5],inline=True)
							page3.add_field(name='Aircrafts',value=list_of_targets[x][6],inline=True)
							page3.add_field(name='Ships',value=list_of_targets[x][7],inline=True)
							page3.add_field(name='Last bank deposit',value=today_date-datetime.strptime(list_of_targets[x][8],"%Y-%m-%dT%H:%M:%S"),inline=True)
							x=x+1
							page3.set_footer(text='Page 3/3')
					page2.set_footer(text=f'Page 2/{len(embeds)}')	
					page1.set_footer(text=f'Page 1/{len(embeds)}')	
					paginator = DiscordUtils.Pagination.CustomEmbedPaginator(ctx, remove_reactions=True)
					paginator.add_reaction('⏮️', "back")
					paginator.add_reaction('⏹️', "lock")
					paginator.add_reaction('⏭️', "next")
					await paginator.run(embeds)
				else:
						page1.set_footer(text='Page 1/1')
						if len(list_of_targets)==0:
							page1.description='Looks like there are no targets in your range, try out other filters to see if you can get any targets.\nFor more info on filters use ;help raid'
						await ctx.send(embed=page1)
			else:
				page1.title='Register'
				page1.description='Usage : `;register <nation id|nation link>`'
				await ctx.send(content="You must be registered to use this command",embed=page1)	
		else:
			await ctx.send('Your subscription has expired, please renew your subscription to keep using the bot')
	else:
		await ctx.send('Your server needs a subscription to use this feature')				

@client.command()
async def register(ctx,link):
	if link.startswith('http'):
		nation_id=int(link[37:])
	else:
		nation_id=link
	update_registered_nations(ctx.author.id,ctx.message.author,nation_id)
	await ctx.send("Successfully registered")
		
@client.command()
async def set_build(ctx,*,values):
	alliance_id=get('alliance_id',ctx.author.id)
	values=eval(values)
	min_infra=values['infra_needed']
	for x in ['infra_needed','imp_total','imp_barracks','imp_factory','imp_hangars','imp_drydock']:
		values.pop(x)
	values=str(values)
	connection=sqlite3.connect('politics and war.db')
	value_to_insert='insert into build values(%s,%s,"%s") on conflict(alliance_id,min_infra) do update set build_details="%s"'	% (alliance_id,min_infra,values,values)
	connection.execute(value_to_insert)
	connection.commit()
	connection.close()
	await ctx.send(f'Build stored for minimum infra {min_infra}')

@client.command()
async def set_defcon(ctx,values):
	alliance_id=get('alliance_id',ctx.author.id)
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	value_to_insert="insert into defcon values (%s,%s,%s,%s,%s) on conflict(alliance_id) do update set barracks=%s,factory=%s,hangar=%s,drydock=%s" % (alliance_id,values[:1],values[2:3],values[4:5],values[6:7],values[:1],values[2:3],values[4:5],values[6:7])
	cursor.execute(value_to_insert)
	connection.commit()
	cursor.close()
	connection.close()
	await ctx.send(f'Defcon for {get("alliance",ctx.author.id)} has been updated')

@commands.is_owner()	
@client.command()
async def update(ctx):
	asyncio.create_task(repeat_every_n_seconds('update_trade_price',7200))
	asyncio.create_task(repeat_every_n_seconds('update_nation_data',300))
	await asyncio.sleep(5)
	asyncio.create_task(repeat_every_n_seconds('update_loot_data',900))	
	await ctx.send("done")		

@client.command()
async def wars(ctx,*,_id=None):
	if _id==None:
		_id=str(ctx.author.id)
	nation_id=await nation_id_finder(ctx,_id)
	active_wars=get_wars(nation_id)
	off_wars=discord.Embed()
	def_wars=discord.Embed()
	def_wars.title='Defensive Wars'
	off_wars.title='Offensive Wars'
	counter_off,counter_def=1,1
	display_elements=['War Type','Ground Control','Air Superiority','Naval Blockade']
	for x in active_wars: 
		if int(x['attid'])==nation_id:
			i=0
			text=f"Defender:[{get_unregistered('nation',x['defid'])}](https://politicsandwar.com/nation/id={x['defid']})\n"
			for keys in x:
				if 'id' not in keys:
					if keys=='war_type':
						text=text+f"{display_elements[i]}:{x[keys]}\n"
					elif x[keys]!='0': 
						text=text+f"{display_elements[i]}:{get_unregistered('nation',x[keys])}\n"			
					i+=1	
			off_wars.add_field(name=f'{counter_off}.https://politicsandwar.com/nation/war/timeline/war={x["id"]}',value=text,inline=False)
			counter_off+=1
		else:
			i=0
			text=f"Aggressor:[{get_unregistered('nation',x['attid'])}](https://politicsandwar.com/nation/id={x['attid']})\n"
			for keys in x:
				if 'id' not in keys:
					if keys=='war_type':
						text=text+f"{display_elements[i]}:{x[keys]}\n"
					elif x[keys]!='0': 
						text=text+f"{display_elements[i]}:{get_unregistered('nation',x[keys])}\n"		
					i+=1
			def_wars.add_field(name=f'{counter_def}.https://politicsandwar.com/nation/war/timeline/war={x["id"]}',value=text,inline=False)
			counter_def+=1
	await ctx.send(embed=off_wars)	
	await ctx.send(embed=def_wars)

@client.command()
async def who(ctx,*,discord_name):
	nation_id=await nation_id_finder(ctx,discord_name)
	nation_data=get_unregistered('*',nation_id)
	discord_id=get('discord_id',nation_id,'registered_nations.nation_id')
	if isinstance(nation_data,tuple):
		embed=discord.Embed()
		embed.title=f'{nation_data[1]}'
		embed.url=f'https://politicsandwar.com/nation/id={nation_data[0]}'
		if discord_id!=None:
			embed.add_field(name='Discord id',value=f'<@{discord_id}>',inline=True)	
		embed.add_field(name='Score',value=nation_data[13],inline=True)
		embed.add_field(name='Offensive War Range',value=f'{int(0.75*nation_data[13])}-{int(1.75*nation_data[13])}',inline=True)
		embed.add_field(name='Defensive War Range',value=f'{int(nation_data[13]/1.75)}-{int(nation_data[13]/0.75)}',inline=True)
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
		alliance_id=aa_finder(discord_name)
		alliance_data=get_unregistered('cities,offensive_wars,defensive_wars,score,soldiers,tanks,aircraft,ships,missiles,nukes',alliance_id,'alliance_position<>1 and alliance_id',True)
		if alliance_id!=[]:	
			total_stats=[0 for x in alliance_data[0]]
			for y in range(0,len(alliance_data)):
				temp=[x for x in alliance_data[y]]
				total_stats=[total_stats[i]+temp[i] for i in range(0,len(temp))]
			embed=discord.Embed()
			embed.title=f"{(get_unregistered('alliance',alliance_id,'alliance_id'))}({len(alliance_data)} nations)"
			embed.url=f'https://politicsandwar.com/alliance/id={alliance_id}'
			just_list=['Cities','Offensive Wars','Defensive Wars','Score','Soldiers','Tanks','Aircraft','Ships','Missiles','Nukes']	
			for x in range(0,len(just_list)):
				embed.add_field(name=just_list[x],value=total_stats[x],inline=True)
			await ctx.send(embed=embed)				
		else:			
			await ctx.send('Invalid nation/allinace')

@client.command()
async def help(ctx,command_name=None):
	embed=discord.Embed()
	if command_name==None:
		embed.title='Help'
		embed.description='List of commands\nUse ;help <command name> to get more info about the specific command'
		embed.add_field(name='Register',value='registers you to the bot')
		embed.add_field(name='Raid',value='get targets')
		embed.add_field(name='Who',value='displays nation information')
		embed.add_field(name='Nation',value='displays your nation registered to the bot')
		embed.add_field(name='Inactivity',value='inactivity length of members')
		embed.add_field(name='Check_color',value='checks if all the members have same color bloc as the alliance')
		embed.add_field(name='Set_defcon',value='Sets defcon for your alliance')
		embed.add_field(name='Set_build',value='Sets the build required for the particular infra level')
		embed.add_field(name='Audit',value='Audits your nation on the basis of criteria set by your alliance')
	else:
		command_name=command_name.lower()
		if command_name=='register':	
			embed.title='Register'
			embed.description='Usage: ;register <nation id|nation link>'
		
		if command_name=='raid':
			embed.title='Raid'
			embed.description='Usage: ;raid'
			embed.add_field(name='Filters',value='1. -i <inactivity days in numbers> [Defaults to 3 if filter not used]\n2. -b <True|False> [gets beige targets,defaults to false if filter not used]\n3. -aa <alliance id(s)> [gets targets in the given alliance,defaults to 0 or none if filter not used]\n4. -app <True|False> [gets target applicants from all alliance,defaults to False]\n5. -all_nations <True|False> [looks for targets in none as well as all other alliance, defaults to False]')
		if command_name=='who':
			embed.title='Who'
			embed.description='Usage: ;who <nation name|@user>\n Takes nation name,leader name,@user and nation id as argument'
		if command_name=='nation':
			embed.title='Nation'
			embed.description='Usage: ;nation\n Gets the nation you are registered to'
		if command_name=='inactivity':
			embed.title='Inactivity'
			embed.description='Usage: ;inactivity\n Displays all nations which are inactive for more than 5 days in the alliance'		
		if command_name=='check_color':
			embed.title='Check_color'
			embed.description='Usage: ;check_color\n Displays all nations that are not in the correct color trade bloc'
		if command_name=='set_defcon':
			embed.title='Set_defcon'
			embed.description='Usage: ;set_defcon <values>\n Example Usage: ;set_defcon 5/0/0/0 (sets defcon to 5 barracks,0 factory,0 hangar and 0 drydock)'
		if command_name=='set_build':
			embed.title='Set_build'
			embed.description='Usage: ;set_build <values>'
		if command_name=='audit':
			embed.title='Audit'	
			embed.description='Usage: ;audit <nation id>\n Defcon and build must be set for your alliance for full functionality'				
	await ctx.send(embed=embed)					

@client.command()
async def copy_db(ctx):
	url = 'http://192.168.1.6:5000/'
	files = {'file': open('politics and war.db', 'rb')}
	async with httpx.AsyncClient(timeout=20) as client:
		response = await client.post(url, files=files)
		print(response)

client.run(os.environ['DISCORD_TOKEN'])		