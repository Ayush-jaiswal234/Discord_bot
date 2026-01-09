import pnwkit
from discord.ext import tasks
import aiosqlite
from scripts import nation_data_converter
from datetime import datetime
import discord

class beige_watcher:
	def __init__(self,client) -> None:
		self.channel = client.get_channel(1367778031439057076) # wap channel:  1254619896290213888,715222394318356541
		self.kit = pnwkit.QueryKit("2b2db3a2636488")
		self.nation_list = []
		self.result = {}
		self.embed = discord.Embed()
		self.get_list_in_beige.start()

	@tasks.loop(minutes=5,reconnect=True)
	async def get_list_in_beige(self):
		async with aiosqlite.connect('pnw.db') as db:
			async with db.execute('select nation_id from all_nations_data where color=0') as cursor:
				nation_list = await cursor.fetchall()
		self.nation_list = [i[0] for i in nation_list]

	async def get_prices(self,db):
		cursor= await db.execute("select * from trade_prices")
		price= await cursor.fetchone()
		await cursor.close()
		return price	



	async def loot_calculator(self,nation_id):
		async with aiosqlite.connect('pnw.db') as db:
			prices = await self.get_prices(db)	
			db.row_factory =aiosqlite.Row
			async with db.execute(f'select * from loot_data where nation_id={nation_id}') as cursor:
				loot = await cursor.fetchone()
				loot = list(loot)
			async with db.execute(f'select war_policy from all_nations_data where nation_id ={nation_id}') as cursor:	
				war_policy = await cursor.fetchone()
		if loot!=None:
			policy_modifer = 1 
			if war_policy['war_policy'] ==5:
				policy_modifer = 1.4
			total_worth = loot[2]*0.14/policy_modifer
			for x in range(0,len(prices)):
				total_worth+= (int(loot[x+3]*0.14/policy_modifer)*prices[x])
				loot[x+3] = loot[x+3]/policy_modifer
			return (total_worth,loot)
		else:
			return None 

	async def beige_leave_handler(self,nation_data):
		if nation_data.id in self.nation_list:
			if nation_data.color != 'beige':
				nation_data = nation_data.to_dict()
				loot = await self.loot_calculator(nation_data['id'])
				if loot:
					nation_data['loot'] = int(loot[0])
				else:
					nation_data['loot'] = 'No loot info found'
				
				await self.send_alert(nation_data)

	async def start(self):
		await self.kit.subscribe("nation", "update", {"include":["color","id"]}, self.beige_leave_handler)


	async def send_alert(self,target):
		self.embed.title = f"Target: {target['nation']}"
		if type(target['loot'])==int:
			self.embed.description = f"Total loot: ${target['loot']:,.2f}"
		else:
			self.embed.description = target['loot']

		self.embed.add_field(name="Nation info",
						value=f"Target: [{target['nation']}](https://politicsandwar.com/nation/war/declare/id={target['nation_id']})\n"
							f"Alliance: [{target['alliance']}](https://politicsandwar.com/alliance/id={target['alliance_id']})\n"
							"```js\n"
							f"Cities: {target['cities']} \n"
							f"Average Infra: {target['avg_infra']}\n"
							f"Last Deposit: {target['last_deposit']}\n"
							f"Last War Loss: {nation_data_converter.time_converter(datetime.strptime(target['war_end_date'],'%Y-%m-%dT%H:%M:%S'))}```",
							inline=False)
		self.embed.add_field(name="Military info",
						value=f"```js\n"
							f"Soldiers: {target['soldiers']:<8,}"
							f"Tanks: {target['tanks']:<8,}\n"
							f"Aircraft: {target['aircraft']:<8,}"
							f"Ships: {target['ships']:<8,}```",
							inline=False)	
		
		await self.channel.send(f'This nation just left beige now',embed=self.embed)	
