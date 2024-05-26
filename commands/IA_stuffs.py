import requests,discord,DiscordUtils
from datetime import datetime,timedelta
from commands.scripts.nation_data_converter import position 

def aa_color_compare(alliance_id):
	nation_query="""{
       		nations(first:500,alliance_id:%s,vmode:false){
            	data{
					id
					color
					alliance_position
            		}
       			}      
			}""" %(alliance_id)
	query="""{
		alliances(id:%s,first:1){ 
			data{
				color
			}
		}	
	}"""% (alliance_id)
	fetchdata=requests.post('https://api.politicsandwar.com/graphql?api_key=10433a4b8a7dec',json={'query':query})
	fetchdata=fetchdata.json()
	nation_data=requests.post('https://api.politicsandwar.com/graphql?api_key=10433a4b8a7dec',json={'query':nation_query})
	nation_data=nation_data.json()
	color_list=[(x['id'],x['color']) for x in nation_data['data']['nations']['data'] if x['alliance_position']!='APPLICANT' and x['color']!=fetchdata['data']['alliances']['data'][0]['color'] ]
	return fetchdata['data']['alliances']['data'][0]['color'],color_list		
pass

async def not_on_color(ctx,color,data):
	pages=len(data)/25
	if isinstance(pages,float):
		pages=int(pages+1)
	embeds=[discord.Embed() for x in range(0,pages)]
	for x in embeds: 
		x.title=f'Nations not on {color.capitalize()}'
	i,index=1,0
	for x in data:
		embeds[index].add_field(name=f'{i}.https://politicsandwar.com/nation/id={x[0]}',value=f'Color:{x[1]}')
		if i%25==0:
			index=index+1
		i+=1	
	if len(embeds)>1:
		paginator = DiscordUtils.Pagination.CustomEmbedPaginator(ctx, remove_reactions=True)
		paginator.add_reaction('⏮️', "back")
		paginator.add_reaction('⏹️', "lock")
		paginator.add_reaction('⏭️', "next")
		await paginator.run(embeds)	
	else:
		await ctx.send(embed=embeds[0])

async def inactive_players(ctx,alliance_id):
	inactive_data=requests.get(f'https://politicsandwar.com/api/nations/?key=10433a4b8a7dec&alliance_id={alliance_id}')		
	inactive_data=inactive_data.json()
	date=datetime.now()
	inactive_list=[(x['nationid'],f'{x["minutessinceactive"]//1440} days,{(x["minutessinceactive"]-((x["minutessinceactive"]//1440)*1440))//60} hours',position(x['allianceposition'])) for x in inactive_data['nations'] if x['minutessinceactive']>4320]
	pages=len(inactive_list)/25
	if isinstance(pages,float):
		pages=int(pages+1)
	embeds=[discord.Embed() for x in range(0,pages)]
	for x in embeds: 
		x.title='Inactive nations'
	i,index=1,0
	for x in inactive_list:
		embeds[index].add_field(name=f'{i}.https://politicsandwar.com/nation/id={x[0]}',value=f'Last active:{x[1]}\nPosition:{x[2]}')
		if i%25==0:
			index=index+1
		i+=1	
	if len(embeds)>1:
		paginator = DiscordUtils.Pagination.CustomEmbedPaginator(ctx, remove_reactions=True)
		paginator.add_reaction('⏮️', "back")
		paginator.add_reaction('⏹️', "lock")
		paginator.add_reaction('⏭️', "next")
		await paginator.run(embeds)	
	else:
		await ctx.send(embed=embeds[0])
pass