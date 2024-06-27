import discord
from discord.ext import tasks
import pnwkit
import os
import httpx

async def check_the_rss(subscribe_data):
    subscribe_data = subscribe_data.to_dict()
    if subscribe_data['buy_or_sell']=='sell' and subscribe_data['accepted']==0:
        profit = (result[f'{subscribe_data["offer_resource"]}']['best_sell_offer']['price']-subscribe_data['price'])*subscribe_data['offer_amount']
        condition1 = profit>=500000
        condition2 = (result[f'{subscribe_data["offer_resource"]}']['best_sell_offer']['price']-subscribe_data['price'])/result[f'{subscribe_data["offer_resource"]}']['best_sell_offer']['price']>=0.01
        if condition1 and condition2:
            link=f'https://politicsandwar.com/index.php?id=26&display=world&resource1={subscribe_data["offer_resource"]}&buysell=sell&ob=price&od=DEF&maximum=15&minimum=0&search=Go'
            await channel.send(f"""<@&1254752332273418301> 
**{subscribe_data['offer_amount']:,} {subscribe_data['offer_resource']} is being sold for ${subscribe_data['price']:,}**
Last Sell price: ${result[f'{subscribe_data["offer_resource"]}']['best_sell_offer']['price']:,}
Last Buy price: ${result[f'{subscribe_data["offer_resource"]}']['best_buy_offer']['price']:,}
**Minimum Profit: ${profit:,}**
{link}""")
            print(subscribe_data["id"])
            check_if_bought = await kit.subscribe("trade","update",{"original_trade_id":subscribe_data["id"],"id":subscribe_data["id"]},check_bought) 
            check_if_deleted = await kit.subscribe("trade","delete",{"id":subscribe_data["id"]},check_delete)
            print(check_if_bought,check_if_deleted)
            if check_if_bought or check_if_deleted:
                await check_if_bought.unsubscribe()
                await check_if_deleted.unsubscribe()

async def check_bought(bought_data):
    print(bought_data.to_dict())
    await channel.send(f"{bought_data['offer_amount']} was bought")

async def check_delete(delete_data):
    await channel.send("Offer deleted by sender")
    return True   

            
intents = discord.Intents.default()	
intents.message_content = True
client = discord.Client(intents=intents)
kit = pnwkit.QueryKit("2b2db3a2636488")



@client.event
async def on_ready():  
    global channel
    update_trades.start()
    subscription = await kit.subscribe("trade","create",{"type":"Global","accepted":0},check_the_rss)
   # async for trade in subscription:
    #    trades= trade.to_dict()
     #   print(trades)
    channel=client.get_channel(715222394318356541) # wap channel:  1254619896290213888,715222394318356541
    print(channel)

@tasks.loop(minutes=1)
async def update_trades():
    global result 
    query = "{top_trade_info {resources {resource best_buy_offer {price offer_amount}best_sell_offer {price offer_amount}}}}"
    api_key='2b2db3a2636488'
    async with httpx.AsyncClient() as httpx_client:
        fetchdata = await httpx_client.post(f'https://api.politicsandwar.com/graphql?api_key={api_key}',json={'query':query})
    fetchdata=fetchdata.json()['data']['top_trade_info']['resources']
    result ={}
    for item in fetchdata:
        if item['resource']=='credit':
            item['resource']='credits'
        result[item['resource']]={
            'best_buy_offer':item['best_buy_offer'],
            'best_sell_offer':item['best_sell_offer']
        }

client.run(os.environ['DISCORD_TOKEN'])		