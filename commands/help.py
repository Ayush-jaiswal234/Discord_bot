from discord.ext import commands
import discord

class help_commands(commands.Cog):
    def __init__(self,bot):
        self.bot = bot


    @commands.hybrid_group(name='help',invoke_without_command=True)
    async def help(self,ctx):
        emb = discord.Embed()
        emb.title='Help'
        emb.description='List of commands\nUse ;help <command name> to get more info about the specific command'
        emb.add_field(name='Register',value='registers you to the bot')
        emb.add_field(name='Raid',value='get targets')
        emb.add_field(name='Who',value='displays nation information')
        emb.add_field(name='Nation',value='displays your nation registered to the bot')
        emb.add_field(name='Inactivity',value='inactivity length of members')
        emb.add_field(name='Check_color',value='checks if all the members have same color bloc as the alliance')
        emb.add_field(name='Set_defcon',value='Sets defcon for your alliance')
        emb.add_field(name='Set_build',value='Sets the build required for the particular infra level')
        emb.add_field(name='Audit',value='Audits your nation on the basis of criteria set by your alliance')
        await ctx.send(embed=emb)

    @help.command(name="register",description="How to register to the bot")
    async def register(self,ctx):
        emb = discord.Embed()
        emb.title='Register'
        emb.description='Usage: ;register <nation id|nation link>'
        await ctx.send(embed=emb)
