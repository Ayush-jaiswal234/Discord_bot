import discord
from scripts import nation_data_converter
import httpx,aiosqlite

async def get_prices():
	async with aiosqlite.connect('pnw.db') as db:
		db.row_factory = aiosqlite.Row
		cursor= await db.execute("select * from trade_prices")
		price= await cursor.fetchone()
		await cursor.close()
	return price	
pass

async def mods_data(nation_id):
	api_v3_link='https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab'
	query=f"""{{
			nations(id:{nation_id}){{
				data{{
					arms_stockpile,bauxite_works,emergency_gasoline_reserve,iron_works,uranium_enrichment_program
				}}
			}} }}"""
	async with httpx.AsyncClient() as client:
		fetchdata=await client.post(api_v3_link,json={'query':query},timeout=None)
		fetchdata = fetchdata.json()["data"]['nations']['data'][0]

	mods = {'munitions':1,'steel':1,'aluminum':1,'gasoline':1,'ura':1}
	if fetchdata["arms_stockpile"]:
		mods['munitions'] =1.34

	if fetchdata["iron_works"]:
		mods['steel'] = 1.36

	if fetchdata["bauxite_works"]:
		mods['aluminum'] = 1.36	

	if fetchdata["emergency_gasoline_reserve"]:
		mods['gasoline'] = 2

	if fetchdata["uranium_enrichment_program"]:
		mods['uranium'] = 2 	

	return mods
	raws_rev ={"uranium":0,"coal":0,"oil":0,"iron":0,"lead":0,"bauxite":0}
	

	raws_rev["uranium"] += 3*manu_plants*(1+(manu_plants*12.5-12.5)/100)*ura_mod*city_count


	raws_rev["coal"] += 3*raw_mines*(1+(raw_mines*5.555-5.55)/100)*city_count
	raws_rev["oil"] += 3*raw_mines*(1+(raw_mines*5.555-5.55)/100)*city_count
	raws_rev["iron"] += 3*raw_mines*(1+(raw_mines*5.555-5.55)/100)*city_count
	raws_rev["bauxite"] += 3*raw_mines*(1+(raw_mines*5.555-5.55)/100)*city_count
	raws_rev["lead"] += 3*raw_mines*(1+(raw_mines*5.555-5.55)/100)*city_count
	
	raws_rev["coal"] -= 3*city["steel_mill"]*(1+(city["steel_mill"]*12.5-12.5)/100)*steel_mod	

	raws_rev["oil"] -= 3*city["oil_refinery"]*(1+(city["oil_refinery"]*12.5-12.5)/100)*gas_mod


	raws_rev["iron"] -= 3*city["steel_mill"]*(1+(city["steel_mill"]*12.5-12.5)/100)*steel_mod	

	raws_rev["lead"] -= 6*city["munitions_factory"]*(1+(city["munitions_factory"]*12.5-12.5)/100)*muni_mod

	raws_rev["bauxite"] -= 3*city["aluminum_refinery"]*(1+(city["aluminum_refinery"]*12.5-12.5)/100)*alum_mod

class ManuPersistentView(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=None)

	@discord.ui.button(label="Manufacutred Resource", custom_id="manu", style=discord.ButtonStyle.blurple)
	async def get_manu_callback(self, interaction, button):
		nation_data = await nation_data_converter.get('all_nations_data.nation_id,continent,cities',interaction.user.id)
		print(nation_data)
		mods = await mods_data(nation_data[0])
		city_count = nation_data[2]
		prices = await get_prices()
		raws_available = nation_data_converter.continent_raws(nation_data[1])
		raws_rev = {}
		for rss in raws_available.split(','):
			if rss !="uranium":
				raws_rev[rss] = 3*10*(1+(10*5.555-5.55)/100)*city_count*prices[rss]
			else:
				raws_rev[rss] += 3*5*(1+(5*12.5-12.5)/100)*mods[rss]*city_count*prices[rss]
		best_raw = max(raws_rev,key=raws_rev.get)
		print(nation_data)
		await interaction.response.send_message(f"This is your nation https://politicsandwar.com/nation/id={nation_data[0]} and no you shouldn't produce any manu.\n Best raw: {best_raw.upper()} = **${raws_rev[best_raw]}** per day")