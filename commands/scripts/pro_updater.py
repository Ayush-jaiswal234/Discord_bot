import threading,sqlite3,requests,time,re
from nation_data_converter import get_unregistered

def update_nation_data():
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	start_time=time.time()
	request_url='https://politicsandwar.com/api/v2/nations/4681b2ff6598e9/&min_score=20'
	nation_data=requests.get(request_url)
	nation_data=nation_data.json()
	cursor.execute('delete from all_nations_data')
	text=''
	for x in nation_data['data']:
		nation_tuple=(f"'{x[keys]}'" if isinstance(x[keys],str) else str(x[keys]) for keys in x)
		text= ','.join(nation_tuple)
		insert_data=f"insert into all_nations_data values ({text})"
		cursor.execute(insert_data)
	connection.commit()
	end_time=time.time()
	print(f'Time nation:{end_time-start_time}')
	cursor.close()
	connection.close()
	threading.Timer(7200.0,update_nation_data).start()
pass

def update_loot_data():
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	query="""{
			wars(days_ago:5,active:false){
			id,date,turnsleft,attid,defid,war_type,winner
			}
	}"""
	all_war_data=requests.get('https://api.politicsandwar.com/graphql?api_key=10433a4b8a7dec',json={'query':query})
	all_war_data=all_war_data.json()
	all_war_data=all_war_data['data']['wars']		
	print(len(all_war_data))
	i=1	
	for x in all_war_data:
		print(i)
		if x['turnsleft']<1 and x['winner']!=0:
			war_data=requests.get(f'https://politicsandwar.com/api/war-attacks/key=10433a4b8a7dec&war_id={x["id"]}')
			war_data=war_data.json()
			for y in war_data['war_attacks']:
				if y['attack_type']=='victory':
					loot=" ".join(y['note'].split())
					loot=loot[(loot.find('looted ')+7):(loot.find('.'))]
					loot=loot.replace(',','')
					loot_info=re.findall('[0-9]{1,}',loot)
					if x['winner']==x['attid']:
						loser=x['defid']
					else:
						loser=x['attid']
					loser_war_policy=get_unregistered('war_policy',loser)
					winner_war_policy=get_unregistered('war_policy',x['winner'])
					if x['war_type']=='RAID':
						base_modifier=10
					elif (x['war_type']=='ATTRITION'and x['winner']==x['defid']) or x['war_type']=='ORDINARY':
						base_modifier=5
					else:
						base_modifier=2.5		
					print(winner_war_policy)
					print(loser_war_policy)
					winner_modifier,loser_modifier=0,0	
					if loser_war_policy==2:
						loser_modifier=0.2
					elif loser_war_policy==5:
						loser_modifier=-0.4
					elif loser_war_policy==8:
						loser_modifier=0.2		
					if winner_war_policy==6:
						winner_modifier=0.4
					elif winner_war_policy==1:
						winner_modifier=-0.2
					loot_modifier=base_modifier+winner_modifier*base_modifier+loser_modifier*base_modifier	
					print(loot_info)
					print(base_modifier,winner_modifier,loser_modifier,loot_modifier)
					loot_info=[str(round(((int(x)*100)/loot_modifier)-int(x),2)) for x in loot_info]	
					data_to_insert=f"insert into loot_data values ({x['id']}, '{x['date']}', {loser}, {', '.join(loot_info)}, 'xyz') on conflict(nation_id) do update set war_id={x['id']},date='{x['date']}',money={loot_info[0]},coal={loot_info[1]},oil={loot_info[2]},uranium={loot_info[3]},iron={loot_info[4]},bauxite={loot_info[5]},`lead`={loot_info[6]},gasoline={loot_info[7]},munitions={loot_info[8]},steel={loot_info[9]},aluminum={loot_info[10]},food={loot_info[11]},loss_or_spy_date='xyz'"
					print(data_to_insert)
					cursor.execute(data_to_insert)
					print(loot)
					print(loot_info)
		i=i+1			
	connection.commit()				

	# cursor.execute('select war_id,nation_id,end_date where war_id')
	# old_data=cursor.fetchall()
	cursor.close()
	connection.close()
pass

def update_trade_price():
	start_time=time.time()
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	update_table="delete from trade_prices"
	cursor.execute(update_table)
	query="""{
			tradeprices(limit:1){
				coal,oil,uranium,iron,bauxite,lead,gasoline,munitions,steel,aluminum,food
			}
		}"""
	fetchdata=requests.post('https://api.politicsandwar.com/graphql?api_key=10433a4b8a7dec',json={'query':query})
	fetchdata=fetchdata.json()
	trade_data=(str(fetchdata['data']['tradeprices'][0][x]) for x in fetchdata['data']['tradeprices'][0])
	text=','.join(trade_data)
	sql_insert_to_table=f"insert into trade_prices values ({text})"
	cursor.execute(sql_insert_to_table)
	connection.commit()
	cursor.close()
	connection.close()
	end_time=time.time()
	print(f'Time trade={end_time-start_time}')
	threading.Timer(7200.0,update_trade_price).start()
pass

update_loot_data()	