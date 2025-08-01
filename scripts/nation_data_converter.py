from discord.ext import commands
import aiosqlite
import datetime

def domestic_policy(number):
	switcher={
	1:'Manifest Destiny',
	2:'Open Markets',
	3:'Technological Advancement',
	4:'Imperialism',
	5:'Urbanization',
	0:'Rapid Expansion'
	}
	return switcher.get(number)
pass

def war_policy(number):
	switcher={
		1:'Attrition',
		2:'Turtle',
		3:'Blitzkrieg',
		4:'Fortress',
		5:'Moneybags',
		6:'Pirate',
		7:'Tactician',
		8:'Guardian',
		9:'Covert',
		10:'Arcane'
	}
	return switcher.get(number)
pass

def continent(number):
	switcher={
	1:'North America',
	2:'South America',
	3:'Europe',
	4:'Africa',
	5:'Asia',
	6:'Australia',
	7:'Antarctica',
	"na":"north_america",
	"sa":"south_america",
	"eu":"europe",
	"af":"africa",
	"as":"asia",
	"au":"australia",
	"an":"antarctica"
	}
	return switcher.get(number)
pass

def continent_raws(number):
	switcher={
	1:'coal,iron,uranium',
	2:'oil,bauxite,lead',
	3:'coal,iron,lead',
	4:'oil,bauxite,uranium',
	5:'oil,iron,uranium',
	6:'coal,bauxite,lead',
	7:'coal,oil,uranium',
	"na":"coal,iron,uranium",
	"sa":"oil,bauxite,lead",
	"eu":"coal,iron,lead",
	"af":"oil,bauxite,uranium",
	"as":"oil,iron,uranium",
	"au":"coal,bauxite,lead",
	"an":"coal,oil,uranium"
	}
	return switcher.get(number)
pass

def color(number):
	switcher={
	0:'Beige',
	1:'Gray',
	2:'Lime',
	3:'Green',
	4:'White',
	5:'Brown',
	6:'Maroon',
	7:'Purple',
	8:'Blue',
	9:'Red',
	10:'Orange', 
	11:'Olive',
	12:'Aqua',
	13:'Black',
	14:'Yellow',
	15:'Pink'
	}
	return switcher.get(number)
pass

def position(number):
	switcher={
	0:'No Alliance',	
	1:'Applicant',
	2:'Member',
	3:'Officer',
	4:'Heir',
	5:'Leader'
	}
	return switcher.get(number)
pass

async def get(search_element,_id,search_using='discord_id'):
	async with aiosqlite.connect('pnw.db') as db:
		async with db.execute(f'select {search_element} from all_nations_data inner join registered_nations on registered_nations.nation_id =all_nations_data.nation_id where {search_using}="{_id}"') as cursor:
			value = await cursor.fetchone()
	if value and len(value)==1:
		value = value[0]
	return value			
pass

async def get_unregistered(search_element,_id,search_using='nation_id',fetchall=False,return_row = False):
	async with aiosqlite.connect('pnw.db') as db:
		if return_row:
			db.row_factory =aiosqlite.Row
		async with db.execute(f"select {search_element} from all_nations_data where {search_using}='{_id}'") as cursor:
			if fetchall==False:
				score = await cursor.fetchone()
			else:
				score= await cursor.fetchall()
	if score !=None and len(score)==1:
		score=score[0]
		if type(score)==(list or tuple) and len(score)==1:
			score=score[0]	
	return score
pass

async def nation_id_finder(ctx,id_or_name):
	try:
		discord_id= await commands.converter.MemberConverter().convert(ctx,id_or_name)
		nation_id = await get('registered_nations.nation_id',discord_id.id)
	except commands.BadArgument:
		if id_or_name.isdigit():
				nation_id=int(id_or_name)
		elif id_or_name.startswith('https://politicsandwar.com/nation'):
			nation_id=int(id_or_name.split('=')[1])	
		else:
			finder=['nation','leader']
			x=0
			nation_id=id_or_name
			while (isinstance(nation_id,str) or nation_id==None) and x<2:
				nation_id=await get_unregistered('nation_id',id_or_name,finder[x])
				x+=1			
	return nation_id	
pass

async def aa_finder(id_or_name):
	if id_or_name.isdigit()	:
		alliance_id=id_or_name
	elif id_or_name.startswith('http'):
		alliance_id=id_or_name[39:]
	else:
		alliance_id = await get_unregistered('alliance_id',id_or_name,'alliance')
	return alliance_id
pass	

def time_converter(war_time,seconds:bool = True):
	now_time = datetime.datetime.now(datetime.UTC)
	difference=now_time.replace(tzinfo=None)-war_time
	minutes,hours=0,0
	seconds=int(str(difference.seconds))
	if seconds>60:
		minutes=int(seconds/60)
		seconds=seconds-(minutes*60)
		if minutes>60:
			hours=int(minutes/60)
			minutes=minutes-hours*60
	if seconds==True:
		return f"{difference.days}d {hours}h {minutes}m {seconds}s ago"
	else:
		return f"{difference.days}d {hours}h {minutes}m ago"		