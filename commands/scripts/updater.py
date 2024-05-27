import aiosqlite,httpx,asyncio,time

api_v3_link='https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab'


async def update_nation_data():
	start_time=time.time()
	db= await aiosqlite.connect('politics and war.db')
	request_url='https://politicsandwar.com/api/v2/nations/819fd85fdca0a686bfab/&min_score=20'
	async with httpx.AsyncClient() as client:
		nationdata= await client.get(request_url,timeout=10)
		nationdata=nationdata.json()
		for x in nationdata['data']:
			nation_id=x['nation_id']
			nation=x['nation']
			leader=x['leader']
			continent=x['continent']
			war_policy=x['war_policy']
			domestic_policy=x['domestic_policy']
			color=x['color']
			alliance_id=x['alliance_id']
			alliance=x['alliance']
			alliance_position=x['alliance_position']
			cities=x['cities']
			offensive_wars=x['offensive_wars']
			defensive_wars=x['defensive_wars']
			score=x['score']
			vmode=x['v_mode']
			vmode_turns=x['v_mode_turns']
			beige_turns=x['beige_turns']
			last_active=x['last_active']
			founded=x['founded']
			soldiers=x['soldiers']
			tanks=x['tanks']
			aircraft=x['aircraft']
			ships=x['ships']
			missiles=x['missiles']
			nukes=x['nukes']
			insert_data="insert into all_nations_data values(%s,'%s','%s',%s,%s,%s,%s,%s,'%s',%s,%s,%s,%s,%s,%s,%s,%s,'%s','%s',%s,%s,%s,%s,%s,%s) on conflict(nation_id) do update set nation='%s',leader='%s',continent=%s,war_policy=%s,domestic_policy=%s,color=%s,alliance_id=%s,alliance='%s',alliance_position=%s,cities=%s,offensive_wars=%s,defensive_wars=%s,score=%s,vmode=%s,vmode_turns=%s,beige_turns=%s,last_active='%s',soldiers=%s,tanks=%s,aircraft=%s,ships=%s,missiles=%s,nukes=%s" % (nation_id,nation,leader,continent,war_policy,domestic_policy,color,alliance_id,alliance,alliance_position,cities,offensive_wars,defensive_wars,score,vmode,vmode_turns,beige_turns,last_active,founded,soldiers,tanks,aircraft,ships,missiles,nukes,nation,leader,continent,war_policy,domestic_policy,color,alliance_id,alliance,alliance_position,cities,offensive_wars,defensive_wars,score,vmode,vmode_turns,beige_turns,last_active,soldiers,tanks,aircraft,ships,missiles,nukes)
			await db.execute(insert_data)   
	await db.commit()
	await db.close()
	end_time=time.time()
	print(f'Time nation={end_time-start_time}')
pass

async def update_loot_data():
	db= await aiosqlite.connect('politics and war.db')
	start_time=time.time()
	query="""{wars(active:false,first:1000,status:INACTIVE){
  				data{
					id
					end_date
					winner_id
					att_id
					attacker{
            			alliance_position
          			}
					def_id  
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
				date=war['end_date'].split('T')[0]
				date_obj=time.strptime(date,"%Y-%m-%d")
				search =('select war_end_date from loot_data where nation_id=%s') %(loser_id)
				cursor = await db.execute(search)
				compare_date=await cursor.fetchone()
				compare_date=time.strptime(compare_date[0],"%Y-%m-%d") if compare_date!= None else compare_date
				if compare_date==None or compare_date<date_obj:
					war_query=f"""{{
				        warattacks(war_id:{war['id']}){{
                        data{{
                            money_looted
                            food_looted
                            coal_looted
                            oil_looted
                            uranium_looted
                            lead_looted
                            iron_looted
                            bauxite_looted
                            gasoline_looted
                            munitions_looted
                            steel_looted
                            aluminum_looted
                            }}	
                        }}
                        }}"""
					loot_data = await client.post(api_v3_link,json={'query':war_query})
					await asyncio.sleep(0.5)
					loot_data=loot_data.json()['data']['warattacks']['data']
					loot_data = loot_data[1] if loser_aa_position not in ["NOALLIANCE","APPLICANT"] else loot_data[0]
					loot=','.join(str(x) for x in loot_data.values())
					loot_with_text=','.join([f"{key.split('_')[0]}={value}" if 'lead' not in key else f"`{key.split('_')[0]}`={value}" for key,value in loot_data.items() ])
					data_to_be_inserted=(f"insert into loot_data values({war['id']},{loser_id},{loot},'{date}') on conflict(nation_id) do update set war_id={war['id']},{loot_with_text},war_end_date='{date}'")
					await db.execute(data_to_be_inserted)
	await db.commit()
	await db.close()
	end_time=time.time()
	print(f'Time loot={end_time-start_time}')
pass		

async def update_trade_price():
    start_time=time.time()
    db= await aiosqlite.connect('politics and war.db')
    update_table="delete from trade_prices"
    await db.execute(update_table)
    query="""{
        top_trade_info {
            market_index
            resources {
            resource
            best_sell_offer {
                price
            }
            }
        }
        }"""
    async with httpx.AsyncClient() as client:
        fetchdata=await client.post(api_v3_link,json={'query':query})
        fetchdata=fetchdata.json()['data']['top_trade_info']['resources']
        fetchdata.pop(-1)
        insert_text=','.join([f"{price['best_sell_offer']['price']}" for price in fetchdata])
        sql_insert_to_table=f"insert into trade_prices values ({insert_text})"
        print(sql_insert_to_table)
        await db.execute(sql_insert_to_table)
    await db.commit()
    await db.close()
    end_time=time.time()
    print(f'Time trade={end_time-start_time}')
pass