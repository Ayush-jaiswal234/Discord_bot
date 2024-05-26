import threading,sqlite3,requests,time

api_v3_link='https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab'


def update_nation_data():
	start_time=time.time()
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	request_url='https://politicsandwar.com/api/v2/nations/819fd85fdca0a686bfab/&min_score=20'
	nationdata=requests.get(f'{request_url}')
	try:
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
			cursor.execute(insert_data)
	except:
		print(nationdata.response,nationdata.text)
	finally:
		connection.commit()
		cursor.close()
		connection.close()
		end_time=time.time()
		print(f'Time nation={end_time-start_time}')
		threading.Timer(300.0,update_nation_data).start()
pass


def update_loot_data():
	connection=sqlite3.connect('politics and war.db')
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
	fetchdata=requests.post(api_v3_link,json={'query':query})	
	fetchdata=fetchdata.json()['data']['wars']['data']
	cursor=connection.cursor()
	biggest_warID=("select war_id from loot_data order by war_id desc")
	cursor.execute(biggest_warID)
	biggest_warID=cursor.fetchall()
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
			cursor.execute(search)
			compare_date=cursor.fetchone()
			compare_date=time.strptime(compare_date[0],"%Y-%m-%d") if compare_date!= None else compare_date
			if compare_date==None or compare_date<date_obj:
				war_query=f"""
				{{
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
				loot_data=requests.post(api_v3_link,json={'query':war_query})	
				try:
					loot_data=loot_data.json()['data']['warattacks']['data']
				except:
					print(loot_data.json())	
				loot_data=loot_data[1] if loser_aa_position not in ["NOALLIANCE","APPLICANT"] else loot_data[0]
				loot=','.join(str(x) for x in loot_data.values())
				loot_with_text=','.join([f"{key.split('_')[0]}={value}" if 'lead' not in key else f"`{key.split('_')[0]}`={value}" for key,value in loot_data.items() ])
				data_to_be_inserted=(f"insert into loot_data values({war['id']},{loser_id},{loot},'{date}') on conflict(nation_id) do update set war_id={war['id']},{loot_with_text},war_end_date='{date}'")
				cursor.execute(data_to_be_inserted)
				
	connection.commit()
	cursor.close()				
	connection.close()
	end_time=time.time()
	print(f'Time loot={end_time-start_time}')
	threading.Timer(900.0,update_loot_data).start()	
pass		

def update_trade_price():
	start_time=time.time()
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	update_table="delete from trade_prices"
	cursor.execute(update_table)
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
	fetchdata=requests.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':query})
	fetchdata=fetchdata.json()['data']['top_trade_info']['resources']
	fetchdata.pop(-1)
	insert_text=','.join([f"{price['best_sell_offer']['price']}" for price in fetchdata])
	print(fetchdata)
	sql_insert_to_table=f"insert into trade_prices values ({insert_text})"
	print(sql_insert_to_table)
	cursor.execute(sql_insert_to_table)
	connection.commit()
	cursor.close()
	connection.close()
	end_time=time.time()
	print(f'Time trade={end_time-start_time}')
	threading.Timer(600.0,update_trade_price).start()
pass