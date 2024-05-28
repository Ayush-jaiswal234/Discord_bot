import aiosqlite,httpx,time

api_v3_link='https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab'


async def update_nation_data():
	start_time=time.time()
	async with aiosqlite.connect('politics and war.db',timeout=20.0) as db:
		await db.execute('delete from all_nations_data')
		request_url='https://politicsandwar.com/api/v2/nations/819fd85fdca0a686bfab/&min_score=20'
		async with httpx.AsyncClient() as client:
			nationdata= await client.get(request_url,timeout=10)
			nationdata=nationdata.json()
			for x in nationdata['data']:
				values =[value if not isinstance(value,str) else f"'{value}'" for value in x.values()]
				text=','.join([f'{value}' for value in values])
				insert_data=f"insert into all_nations_data values ({text})"
				await db.execute(insert_data)   
		await db.commit()
	end_time=time.time()
	print(f'Time nation={end_time-start_time}')
pass

#use pro_updater to improve this code later
async def update_loot_data():
	async with aiosqlite.connect('politics and war.db',timeout=20.0) as db:
		start_time=time.time()
		query="""{wars(active:false,first:1000,status:INACTIVE){
					data{
						id,end_date,winner_id,att_id,def_id
						attacker{
							alliance_position
						}  
						defender{
							alliance_position
						}
					}	
					}	}"""
		async with httpx.AsyncClient() as client:
			fetchdata=await client.post(api_v3_link,json={'query':query})
			fetchdata=fetchdata.json()['data']['wars']['data']
			biggest_warID=("select war_id from loot_data order by war_id desc")
			cursor= await db.execute(biggest_warID)
			biggest_warID = await cursor.fetchall()
			biggest_warID=[x[0] for x in biggest_warID]
			for war in fetchdata:
				if war['winner_id'] != '0':
					loser_id= war['def_id'] if war['winner_id']==war['att_id'] else war['att_id']
					try:
						loser_aa_position=war['defender']['alliance_position'] if war['winner_id']==war['att_id'] else war['attacker']['alliance_position']
					except TypeError:
						loser_aa_position='NOALLIANCE'	
					date=war['end_date'].split('+')[0]
					date_obj=time.strptime(date,"%Y-%m-%dT%H:%M:%S")
					search =('select war_end_date from loot_data where nation_id=%s') %(loser_id)
					cursor = await db.execute(search)
					compare_date=await cursor.fetchone()
					compare_date=time.strptime(compare_date[0],"%Y-%m-%dT%H:%M:%S") if compare_date!= None else compare_date
					if compare_date==None or compare_date<date_obj:
						war_query=f"""{{
							warattacks(war_id:{war['id']}){{
							data{{
								money_looted,food_looted,coal_looted,oil_looted,uranium_looted,lead_looted,iron_looted,bauxite_looted,gasoline_looted,munitions_looted,steel_looted,aluminum_looted
								}}	
							}}
							}}"""
						loot_data = await client.post(api_v3_link,json={'query':war_query})
						if 'Too Many Requests' in str(loot_data):
							break
						loot_data=loot_data.json()['data']['warattacks']['data']
						loot_data = loot_data[1] if loser_aa_position not in ["NOALLIANCE","APPLICANT"] else loot_data[0]
						loot=','.join(str(x) for x in loot_data.values())
						loot_with_text=','.join([f"{key.split('_')[0]}={value}" if 'lead' not in key else f"`{key.split('_')[0]}`={value}" for key,value in loot_data.items() ])
						data_to_be_inserted=(f"insert into loot_data values({war['id']},{loser_id},{loot},'{date}') on conflict(nation_id) do update set war_id={war['id']},{loot_with_text},war_end_date='{date}'")
						await db.execute(data_to_be_inserted)
		await db.commit()
	end_time=time.time()
	print(f'Time loot={end_time-start_time}')
pass		

async def update_trade_price():
	start_time=time.time()
	async with aiosqlite.connect('politics and war.db',timeout=20.0) as db:
		await db.execute("delete from trade_prices")
		query="""{
			tradeprices(first:1){data{
				food,coal,oil,uranium,lead,iron,bauxite,gasoline,munitions,steel,aluminum
  			} }
  			}"""
		async with httpx.AsyncClient() as client:
			fetchdata=await client.post(api_v3_link,json={'query':query})
			fetchdata=fetchdata.json()['data']['tradeprices']['data'][0]
			print(fetchdata)
			insert_text=','.join([f"{price}" for price in fetchdata.values()])
		sql_insert_to_table=f"insert into trade_prices values ({insert_text})"
		print(sql_insert_to_table)
		await db.execute(sql_insert_to_table)
		await db.commit()
	end_time=time.time()
	print(f'Time trade={end_time-start_time}')
pass