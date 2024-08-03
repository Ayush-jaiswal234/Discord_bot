from discord.ext import tasks
import httpx
import pnwkit
import logging
import discord
import aiosqlite
from scripts.nation_data_converter import get_unregistered
from httpx import ReadTimeout,ConnectTimeout

class trade_watcher:
	def __init__(self,client) -> None:
		self.channel = client.get_channel(1254619896290213888) # wap channel:  1254619896290213888,715222394318356541
		self.kit = pnwkit.QueryKit("2b2db3a2636488")
		self.track_ids = []
		self.result = {}
		self.embed = discord.Embed()
		self.update_trades.add_exception_type(KeyError,ReadTimeout,ConnectTimeout)
		self.update_trades.start()

	async def send_message(self,role,type_of_trade,profit,subscribe_data): 
		link=f'https://politicsandwar.com/index.php?id=26&display=world&resource1={subscribe_data["offer_resource"]}&buysell={type_of_trade}&ob=price&od=DEF&maximum=15&minimum=0&search=Go'
		past_tense = 'sold'
		if type_of_trade== 'buy':
			past_tense ='bought'
		await self.channel.send(f"""<@&{role}> 
**{subscribe_data['offer_amount']:,} {subscribe_data['offer_resource']} is being {past_tense} for ${subscribe_data['price']:,}**
Last Sell price: ${self.result[f'{subscribe_data["offer_resource"]}']['best_sell_offer']['price']:,}
Last Buy price: ${self.result[f'{subscribe_data["offer_resource"]}']['best_buy_offer']['price']:,}
**Minimum Profit: ${profit:,}**
{link}""")
		logging.info(subscribe_data["id"])
		check_if_deleted = await self.kit.subscribe("trade","delete",{"id":subscribe_data["id"]},self.check_delete)
		self.track_ids.append({"id":subscribe_data["id"],"delete":False,"amount":subscribe_data["offer_amount"],"buy_sell":past_tense,"message_id":self.channel.last_message_id})    

	async def profit_calculator(self,type_of_trade,last_sell_price,subscribe_data):
		profit = (last_sell_price-1-subscribe_data['price'])*subscribe_data['offer_amount']
		profit_percent = (last_sell_price-1-subscribe_data['price'])/last_sell_price
		if type_of_trade=="sell":
			condition1 = subscribe_data['price']<self.result[f'{subscribe_data["offer_resource"]}']['best_buy_offer']['price']
		else:    
			condition1 = subscribe_data['price']>self.result[f'{subscribe_data["offer_resource"]}']['best_sell_offer']['price']
			profit=-profit
			profit_percent = -profit_percent
		if condition1 and profit>=5000000 and profit_percent>0.022:
			role ="1254752332273418301"
			await self.send_message(role,type_of_trade,profit,subscribe_data)
		elif condition1 and profit>=1000000 and profit<5000000 and profit_percent>0.033: 
			role ="1258312874137223229"
			await self.send_message(role,type_of_trade,profit,subscribe_data)
		elif profit>100000 and profit<1000000 and profit_percent>0.044:
			role ="1258312933427908725"
			await self.send_message(role,type_of_trade,profit,subscribe_data)      
			

	async def check_the_rss(self,subscribe_data):
		subscribe_data = subscribe_data.to_dict()
		if subscribe_data['accepted']==0:
			logging.info(subscribe_data)
			await self.profit_calculator(subscribe_data['buy_or_sell'],self.result[f'{subscribe_data["offer_resource"]}']['best_sell_offer']['price'],subscribe_data)
		
		elif self.track_ids!=[]:
			for ids in self.track_ids:
				if subscribe_data["original_trade_id"]==ids["id"]:
					ids["amount"]=ids["amount"]-subscribe_data["offer_amount"]
					
					self.embed.title = f'{subscribe_data["offer_amount"]} {subscribe_data["offer_resource"]} was {ids["buy_sell"]} from this trade'
					self.embed.description = (f'Sender: [{await get_unregistered("nation",subscribe_data["sender_id"])}](https://politicsandwar.com/nation/id={subscribe_data["sender_id"]})\n'
					f'Receiver: [{await get_unregistered("nation",subscribe_data["receiver_id"])}](https://politicsandwar.com/nation/id={subscribe_data["receiver_id"]})\n'
					f'Amount Remaining: {ids["amount"]}')
					await self.channel.send(embed = self.embed,reference=discord.MessageReference(message_id=ids["message_id"],channel_id=self.channel.id))
			self.track_ids = [x for x in self.track_ids if x["amount"]!=0 and x["delete"]==False]        

	async def check_delete(self,delete_data):
		self.embed.title = f'Trade {delete_data["id"]} deleted'
		async with aiosqlite.connect('pnw.db'):
			self.embed.description = f'Sender: [{await get_unregistered("nation",delete_data["sender_id"])}](https://politicsandwar.com/nation/id={delete_data["sender_id"]})'
		for ids in self.track_ids:
			if delete_data["id"]==ids["id"]:
				await self.channel.send(embed=self.embed,reference=discord.MessageReference(message_id=ids["message_id"],channel_id=self.channel.id))  
				ids["delete"]=True

	async def start(self):
		
		subscription = await self.kit.subscribe("trade","create",{"type":"Global","accepted":0},self.check_the_rss)

	@tasks.loop(seconds=15,reconnect=True)
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


