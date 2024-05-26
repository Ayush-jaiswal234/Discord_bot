import discord

async def nation_command_handler(ctx,nation_info):
	if nation_info==None:
		await ctx.send('You must be registered to use this command')
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
