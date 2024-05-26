import discord

async def guild(ctx,client):
	guilds= await client.fetch_guilds().flatten()
	embed=discord.Embed()
	embed.title='Servers'
	embed.description='The list of the alliances the bot is present in:'
	counter=1
	for guild in client.guilds:
		embed.add_field(name=f'{counter}.{guild.name}',value=f'Server ID:{guild.id}',inline=False)
		counter=counter+1
	await ctx.send(embed=embed)