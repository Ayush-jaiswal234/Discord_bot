import discord
from discord.ext import tasks
import httpx
import os


graphql_link='https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab'
intents = discord.Intents.default()	
intents.message_content = True
client = discord.Client(intents=intents)

api_key='2b2db3a2636488'
query = "{top_trade_info {resources {resource best_buy_offer {price offer_amount}best_sell_offer {price offer_amount sender{nation_name}}}}}"
client =  httpx.AsyncClient()
tasks.add_exception_type = KeyError
last_result = None


@client.event
async def on_ready():    
    global last_result
    fetchdata =await client.post(f'https://api.politicsandwar.com/graphql?api_key={api_key}',json={'query':query})
    channel=client.get_channel(1254619896290213888) # wap channel:  1254619896290213888,715222394318356541
    print(channel)
    fetchdata=fetchdata.json()['data']['top_trade_info']['resources']
    last_result=fetchdata	
    trade_watcher.start(channel)

@tasks.loop(seconds=1.1,reconnect=True)	
async def trade_watcher(channel):
    global last_result
    fetchdata = await client.post(f'https://api.politicsandwar.com/graphql?api_key={api_key}',json={'query':query})
    fetchdata=fetchdata.json()['data']['top_trade_info']['resources']
    resource_no=-1
    for rss in fetchdata:
        resource_no+=1
        condition1 = ((last_result[resource_no]['best_sell_offer']['price']-rss['best_sell_offer']['price'])*rss['best_sell_offer']['offer_amount'])>500000
        condition2 = (last_result[resource_no]['best_sell_offer']['price']-rss['best_sell_offer']['price'])/last_result[resource_no]['best_sell_offer']['price']>=0.02
        if condition1 and condition2:
            link=f'https://politicsandwar.com/index.php?id=26&display=world&resource1={rss["resource"]}&buysell=sell&ob=price&od=DEF&maximum=15&minimum=0&search=Go'
            await channel.send(f"""<@&1254752332273418301> 
**{rss['best_sell_offer']['sender']['nation_name']} sells {rss['best_sell_offer']['offer_amount']:,} {rss['resource']} for ${rss['best_sell_offer']['price']:,}**
Last Sell price: ${last_result[resource_no]['best_sell_offer']['price']:,}
Last Buy price: ${rss['best_buy_offer']['price']:,}
**Minimum Profit: ${((last_result[resource_no]['best_sell_offer']['price']-rss['best_sell_offer']['price'])*rss['best_sell_offer']['offer_amount']):,}**
{link}""")
    
    last_result=fetchdata

client.run(os.environ['DISCORD_TOKEN'])			