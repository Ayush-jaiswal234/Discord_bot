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
		emb.add_field(name='Commands',value=('1. air\t\tAir attack simulation.\n'
											'2. banklootval\t\tGet the value of the bank basing on the beige message from war history.\n'
											'3. fastbeige\t\tGet the five fastest ways to beige an opponent.\n'
											'4. ground\t\tGround attack simulation.\n'
											'5. loot\t\tGet the loot data based on last war loss or spy report\n'
											'6. lootval\t\tGet the value of the nation beige loot basing on the beige message from war history.\n'
											'7. naval\t\t\Naval attack simulation\n'
											'8. pricehistory\t\t\Helps in determination of market prices movement\n'
									   		'9. raid\t\t\Gets raid targets\n'
									   		'10. register\t\t\registers you to the bot\n'
									   		'11. slowbeige\t\t\Get the five slowest ways to beige an opponent. Useful for sitting purposes.\n'
									   		'12. spyopval\t\t\Get the value of the nation beige loot basing on the GATHER INTEL result from notifications.\n'
									   		'13. who\t\t\Displays nation information\n'
									   		'14. wars\t\t\Get the wars a nation is currently in'))
		await ctx.send(embed=emb)

	@help.command(name='air',description='Air attack simulation.')
	async def air(self,ctx):
		emb = discord.Embed()
		emb.title = 'Air'
		emb.description = (';air (AttAircraft) (DefAircraft) -filters\n'
						'Sample command: `;air 1800 900 -b -soldiers`')
		emb.add_field(name='Filters',value=('1. -soldiers	Simulate the airstrike on soldiers\n'
									  		'2. -tanks		Simulate the airstrike on tanks\n'
											'3. -ships		Simulate the airstrike on ships\n'
											'4. -b			Simulate the airstrike with a blitzkrieg war policy\n'
											'5. -f 			Simulate the airstrike on a fortified opponent'))
		await ctx.send(embed=emb)

	@help.command(name='ground',description='Ground attack simulation')
	async def ground(self,ctx):
		emb = discord.Embed()
		emb.title='Ground'
		emb.description=(';ground (AttSoldiers) (AttTanks) (DefSoldiers) (DefTanks) (AttUsesMunis?: True/False) (DefUsesMunis?: True/False) \n'
						'Sample command: `;ground 450000 30000 300000 12500 false true`')
		await ctx.send(embed=emb)
		
	@help.command(name='naval',description='Naval attack simulation.')
	async def naval(self,ctx):
		emb = discord.Embed()
		emb.title = 'Air'
		emb.description = (';naval (AttShips) (DefShips) -filters\n'
						'Sample command: `;naval 500 200 -b -f`')
		emb.add_field(name='Filters',value=('1. -b		Simulate the naval with a blitzkrieg war policy\n'
											'2. -f 		Simulate the naval on a fortified opponent'))
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

	@help.command(name="register",description="How to register to the bot")
	async def register(self,ctx):
		emb = discord.Embed()
		emb.title='Register'
		emb.description='Usage: ;register <nation id|nation link>'
		await ctx.send(embed=emb)    

	@help.command(name="who")
	async def who(self,ctx):
		emb = discord.Embed()
		emb.title = 'Who'
		emb.description = 'Usage: ;who <nation id/link/name |discord user>'
		await ctx.send(embed=emb)	
		

async def setup(bot):
    await bot.add_cog(help_commands(bot))