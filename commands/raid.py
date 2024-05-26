import DiscordUtils,time,discord,sqlite3
from datetime import datetime,timedelta
from commands.scripts.nation_data_converter import *

def get_prices(cursor):
	prices=[]
	list_of_things_to_find=['Coal','Oil','Uranium','Iron','Bauxite','`Lead`','Gasoline','Munitions','Steel','Aluminum','Food']			
	for x in range(0,len(list_of_things_to_find),1):
		things_to_find="select %s from trade_prices" % (list_of_things_to_find[x])
		cursor.execute(things_to_find)
		price=cursor.fetchone()
		price=price[0]
		prices.append(x)
		prices[x]=price
	return prices	
pass

def targets(war_range,inactivity_time,aa,beige,applicants):
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	date=datetime.now().replace(microsecond=0)
	date = date -timedelta(days=inactivity_time)
	targets_list= "select * from loot_data inner join all_nations_data on loot_data.nation_id =all_nations_data.nation_id where score>%s and score<%s %s and vmode=0 and defensive_wars<>3 %s %s and date(last_active)<'%s'" % (war_range[0],war_range[1],beige,aa,applicants,date)
	print(targets_list)
	cursor.execute(targets_list)
	all_targets=cursor.fetchall()
	prices=get_prices(cursor)
	final_list=[]
	for y in range(0,len(all_targets)):
		amount=all_targets[y][4]
		for x in range(0,11):
			amount=amount+(all_targets[y][x+4]*prices[x])
		data_tuple=(all_targets[y][2],amount,all_targets[y][17],all_targets[y][24],all_targets[y][25],all_targets[y][32],all_targets[y][35],all_targets[y][36],all_targets[y][37],all_targets[y][38],all_targets[y][39],all_targets[y][40])	
		final_list.insert(y,data_tuple)	
	cursor.close()
	connection.close()
	final_list.sort(key=lambda x:x[1],reverse=True)
	print(final_list)
	return final_list
pass

async def raid_command_handler(ctx,results,flags):
	if results!=None:
		today_date=datetime.now().replace(microsecond=0)
		today_date=time.strptime(str(today_date),"%Y-%m-%d %H:%M:%S")
		end_date=time.strptime(results[2],"%Y-%m-%d %H:%M:%S")
		if end_date>today_date:
			score=get('score',ctx.author.id)
			war_range=score-score*25/100,score+score*75/100
			aa=flags['aa']
			inactivity_time=flags['i']
			beige='and color<>0'
			applicants=''
			if score!=None:
				if flags['s'] !=None:
					score=flags['s']
				if flags['b']==True:	
					beige=''
				aa=aa.split(',')
				aa=tuple(aa)
				if flags['app']==True and aa[0]=='0':
					applicants='and (alliance_id=0 or alliance_position=1)'
					aa=''	
				elif len(aa)==1 and flags['all_nations']==False:
					aa=f'and alliance_id = {aa[0]}'
				elif len(aa)!=1 and flags['all_nations']==False:
					aa=f'and alliance_id in {aa}'
				else:
					aa=''		
				list_of_targets=targets(war_range,inactivity_time,aa,beige,applicants)
				list_of_targets=[list_of_targets[x] for x in range(0,len(list_of_targets)) if x<9]
				print(list_of_targets,len(list_of_targets))
				if len(list_of_targets)==0:
					embed=discord.Embed()
					embed.title='Targets'
					embed.description='Looks like there are no targets in your range, try out other filters to see if you can get any targets.\nFor more info on filters use ;help raid'
					await ctx.send(embed=embed)
				else:
					pages=len(list_of_targets)/3
					if isinstance(pages,float):
						pages=int(pages+1)
					if pages>3:
						pages=3	
					embeds=[discord.Embed() for x in range(0,pages)]
					for x in range(len(embeds)): 
						embeds[x].title='Targets'
						embeds[x].set_footer(text=f'Page {x+1}/{pages}')
					i,embed_index=0,0	
					while i<len(list_of_targets) and i<10:
						print(i,embed_index)
						loot='Loot:' + '{:,}'.format(list_of_targets[i][1])
						embeds[embed_index].add_field(name=f'{i+1}.https://politicsandwar.com/nation/id={list_of_targets[i][0]}',value=f'{loot}',inline=False)
						embeds[embed_index].add_field(name='Alliance',value=list_of_targets[i][3],inline=True)
						if list_of_targets[i][4]!=0:
							embeds[embed_index].add_field(name='Position',value=position(list_of_targets[i][4]),inline=True)
						if list_of_targets[i][5]!=0:
							embeds[embed_index].add_field(name='Beige',value=f'{list_of_targets[i][5]} turns',inline=True)
						embeds[embed_index].add_field(name='Soldiers',value=list_of_targets[i][6],inline=True)
						embeds[embed_index].add_field(name='Tanks',value=list_of_targets[i][7],inline=True)
						embeds[embed_index].add_field(name='Aircrafts',value=list_of_targets[i][8],inline=True)	
						embeds[embed_index].add_field(name='Ships',value=list_of_targets[i][9],inline=True)	
						i+=1
						if (i)%3==0:
							embed_index=embed_index+1
					paginator = DiscordUtils.Pagination.CustomEmbedPaginator(ctx, remove_reactions=True)
					paginator.add_reaction('⏮️', "back")
					paginator.add_reaction('⏹️', "lock")
					paginator.add_reaction('⏭️', "next")
					await paginator.run(embeds)
			else:
				page1.title='Register'
				page1.description='Usage : `;register <nation id|nation link>`'
				await ctx.send(content="You must be registered to use this command",embed=page1)	
		else:
			await ctx.send('Your subscription has expired, please renew your subscription to keep using the bot')
	else:
		await ctx.send('Your server needs a subscription to use this feature')