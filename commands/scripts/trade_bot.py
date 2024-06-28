from discord.ext import tasks
import httpx
import pnwkit
import logging

class trade_watcher:
    def __init__(self,client) -> None:
        self.channel = client.get_channel(1254619896290213888) # wap channel:  1254619896290213888,715222394318356541
        self.kit = pnwkit.QueryKit("2b2db3a2636488")
        self.track_ids = []
        self.result = {}

    async def profit_calculator(self,type_of_trade,parameter,subscribe_data):
        profit = (parameter-subscribe_data['price'])*subscribe_data['offer_amount']
        
        if type_of_trade=="sell":
            condition2 = (parameter-subscribe_data['price'])/parameter>=0.02  
            condition1 = profit>=500000
        else:    
            condition2 = (parameter-subscribe_data['price'])/parameter <=-0.02
            condition1 = profit<=-500000
        if condition1 and condition2:
            link=f'https://politicsandwar.com/index.php?id=26&display=world&resource1={subscribe_data["offer_resource"]}&buysell={type_of_trade}&ob=price&od=DEF&maximum=15&minimum=0&search=Go'
            past_tense = 'sold'
            if type_of_trade== 'buy':
                past_tense ='bought'
            await self.channel.send(f"""<@&1254752332273418301> 
    **{subscribe_data['offer_amount']:,} {subscribe_data['offer_resource']} is being {past_tense} for ${subscribe_data['price']:,}**
    Last Sell price: ${self.result[f'{subscribe_data["offer_resource"]}']['best_sell_offer']['price']:,}
    Last Buy price: ${self.result[f'{subscribe_data["offer_resource"]}']['best_buy_offer']['price']:,}
    **Minimum Profit: ${abs(profit):,}**
    {link}""")
            logging.log(subscribe_data["id"])
            check_if_deleted = await self.kit.subscribe("trade","delete",{"id":subscribe_data["id"]},self.check_delete)
            self.track_ids.append({"id":subscribe_data["id"],"delete":False,"amount":subscribe_data["offer_amount"],"buy_sell":past_tense}) 

    async def check_the_rss(self,subscribe_data):
        subscribe_data = subscribe_data.to_dict()
        if subscribe_data['accepted']==0:
            if subscribe_data['buy_or_sell']=='sell': 
                await self.profit_calculator(subscribe_data['buy_or_sell'],self.result[f'{subscribe_data["offer_resource"]}']['best_sell_offer']['price'],subscribe_data)
            else:
                await self.profit_calculator(subscribe_data['buy_or_sell'],self.result[f'{subscribe_data["offer_resource"]}']['best_sell_offer']['price'],subscribe_data)    
            
        elif self.track_ids!=[]:
            for ids in self.track_ids:
                if subscribe_data["original_trade_id"]==ids["id"]:
                    ids["amount"]=ids["amount"]-subscribe_data["offer_amount"]
                    await self.channel.send(f'{subscribe_data["offer_amount"]} {subscribe_data["offer_resource"]} was {ids["buy_sell"]} from the above trade')
            track_ids = [x for x in track_ids if x["amount"]!=0 and x["delete"]==False]        

    async def check_delete(self,delete_data):
        await self.channel.send("Offer deleted by sender")  
        for ids in self.track_ids:
            if delete_data["id"]==ids["id"]:
                ids["delete"]=True

    async def on_ready(self):  
        self.update_trades.start()
        subscription = await self.kit.subscribe("trade","create",{"type":"Global","accepted":0},self.check_the_rss)

    @tasks.loop(minutes=1)
    async def update_trades(self): 
        query = "{top_trade_info {resources {resource best_buy_offer {price offer_amount}best_sell_offer {price offer_amount}}}}"
        api_key='2b2db3a2636488'
        async with httpx.AsyncClient() as httpx_client:
            fetchdata = await httpx_client.post(f'https://api.politicsandwar.com/graphql?api_key={api_key}',json={'query':query})
        fetchdata=fetchdata.json()['data']['top_trade_info']['resources']
        for item in fetchdata:
            if item['resource']=='credit':
                item['resource']='credits'
            self.result[item['resource']]={
                'best_buy_offer':item['best_buy_offer'],
                'best_sell_offer':item['best_sell_offer']
            }		