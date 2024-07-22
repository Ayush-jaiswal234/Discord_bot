from discord.ext import commands
import discord

class help_commands(commands.Cog):
	def __init__(self,bot):
		self.bot = bot

	@commands.hybrid_group(name='help',with_app_command=True)
	async def help(self,ctx):
		emb = discord.Embed()
		emb.title='Help'
		emb.description='Use ;help <command name> to get more info about the specific command'
		emb.add_field(name='Commands',value=('1. Register registers you to the bot'
									   '2. Raid gets targets'
									   '3. Who displays nation information'))
		await ctx.send(embed=emb)

	@help.command(name="register",description="How to register to the bot")
	async def register(self,ctx):
		emb = discord.Embed()
		emb.title='Register'
		emb.description='Usage: ;register <nation id|nation link>'
		await ctx.send(embed=emb)    

	@help.command(name="raid",description="info on how to use the raid command")
	async def raid(self,ctx):
		emb = discord.Embed()
		emb.title = 'Raid'
		emb.description = 'Usage: ;raid -filter value'
		emb.add_field(name='Filters',value=('1. -inactivity_days:`n` [Looks for targets inactive for n days, defaults to 0]\n'
										   '2. -beige:`True|False` [gets beige targets,defaults to True if filter not used]\n'
										   '3. -alliances:`alliance id(s)` [gets targets in the given alliance,defaults to 0 or none if filter not used]\n'
										   '4. -beige_turns:`n` [gets targets with maximum beige of n turns,defaults to 216]\n'
										   '5. -all_nations:`True|False` [looks for all targets in the games, defaults to False]\n'
										   '6. -result:`embed|sheets` [The format you want the result in]'))
		await ctx.send(embed=emb)

	@help.command(name="who")
	async def who(self,ctx):
		emb = discord.Embed()
		emb.title = 'Who'
		emb.description = 'Usage: ;who <nation id/link/name |discord user>'
		await ctx.send(embed=emb)	
		

async def setup(bot):
    await bot.add_cog(help_commands(bot))