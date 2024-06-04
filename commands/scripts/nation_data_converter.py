import sqlite3
from discord.ext import commands
import aiosqlite

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
	7:'Antarctica'
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
	1:'Applicant',
	2:'Member',
	3:'Officer',
	4:'Heir',
	5:'Leader'
	}
	return switcher.get(number)
pass

async def get(search_element,_id,search_using='discord_id'):
	async with aiosqlite.connect('politics and war.db') as db:
		async with db.execute(f'select {search_element} inner join registered_nations on registered_nations.nation_id =all_nations_data.nation_id where {search_using}="{_id}"') as cursor:
			value = await cursor.fetchone()
	value = value[0] if value != None else value
	return value			
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