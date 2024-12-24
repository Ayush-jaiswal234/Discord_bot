import httpx

async def spy_target_finder(att_ids,def_ids):
	query = f"""{{alliances(id:[{att_ids},{def_ids}],first:500){{
				data{{
					name,id
					nations(vmode:false){{
						num_cities,id,nation_name,alliance_position,score,nukes,spies,espionage_available,war_policy,central_intelligence_agency,surveillance_network,spy_satellite,spy_attacks
						}}
					}}
				}} }}"""
	
	async with httpx.AsyncClient() as client:
		fetchdata = await client.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':query})
		fetchdata = fetchdata.json()['data']['alliances']['data']
	attackers= []
	defenders = []
	total_spies=0
	for alliances in fetchdata:
		for nation in alliances['nations']:
			if nation['alliance_position']!="APPLICANT":
				nation['alliance']= alliances['name']
				if alliances['id'] in att_ids.split(','):
					attackers.append(nation)
				else:
					if nation['espionage_available'] and (nation['spies']>5 or nation['nukes']>=3):
						defenders.append(nation)	
						total_spies+= nation['spies']
	attackers = sorted(attackers, key=lambda x: (x['spies']),reverse=True)
	if total_spies/(len(defenders)+1)>10:
		defenders = sorted(defenders, key=lambda x: (x['spies'],x['num_cities']),reverse=True)
	else:
		defenders = sorted(defenders, key=lambda x: (x['nukes'] >= 3,x['nukes'] if x['nukes'] >= 3 else x['spies']), reverse=True)
	result = find_top_attackers_efficiently(attackers, defenders)
	return result

def calculate_adjusted_odds(attacker, def_spies,defender, attack_type):
    # Base odds calculation
	odds =[level * 25 + (attacker['spies'] * 100 / ((def_spies * 3) + 1)) for level in range(1,4)]

	if defender['war_policy']=='ARCANE':
		odds = [x * 1.15 for x in odds]
	elif defender['war_policy']=='TACTICIAN':	
		odds = [x * 0.85 for x in odds]
	if attacker['war_policy']=="COVERT":
		odds = [x * 1.15 for x in odds]

	if defender['surveillance_network']:	
		odds = [x/1.1 for x in odds]

	if attack_type == "spy":
		odds = [x/1.5 for x in odds] # Adjust for spy kills
	elif attack_type == "nuke":
		odds = [x/5 for x in odds]    # Adjust for nukes
	
	attack={"odds":odds[2],"level":3,"type":attack_type}	
	if odds[2]-odds[1]<5 or odds[2]>100:
		if odds[1]-odds[0]<5 or (odds[1]>100 and odds[0]>95):
			attack['odds']=odds[0]
			attack['level']=1
		else:
			attack['odds']=odds[1]
			attack['level']=2
				
	return attack

# Find top attackers with adjusted odds
def find_top_attackers_efficiently(attackers, defenders):
    # Tracker for attacker usage
	attacker_slot = {attacker['id']:2-attacker['spy_attacks'] if attacker['central_intelligence_agency'] else 1-attacker['spy_attacks'] for attacker in attackers}
	# Result sheet for top attackers
	result = []
	switcher = {1:'quick',2:'normal',3:'covert'}
	for defender in defenders:
		defender_spies = defender['spies']
		defender_nukes = defender['nukes']
		# Calculate adjusted odds for all attackers against this defender
		odds_list = []
		for attacker in attackers:
			attacker_id = attacker['id']
			if attacker_slot[attacker_id] != 0 and attacker['score']/2.5 <=defender['score']<=attacker['score']*2.5:  # Restrict attacker usage to 2 times
				att_spies = attacker['spies']
				# Adjusted odds for spy attack
				match_info = False
				if defender_spies>5:
					match_info = calculate_adjusted_odds(attacker, defender_spies,defender, attack_type="spy")
					defender_spies -=  min((att_spies- (defender_spies* 0.4)) * 0.335*0.95,(defender_spies*0.25) + 4)
				elif defender_nukes>=3:
					match_info = calculate_adjusted_odds(attacker, defender_spies,defender, attack_type="nuke")
					defender_nukes -= 1
				
				if match_info:	
					odds_list.append({
						"attacker": attacker,
						"optimal_attack":match_info
					})
		if odds_list:
			# Sort attackers by the highest adjusted odds
			odds_list.sort(key=lambda x: (x['attacker']['spies'],x['optimal_attack']['type'],x['optimal_attack']['level'],x['optimal_attack']['odds']),reverse=True)

			# Select top 3 attackers for this defender
			top_attackers = []
			for entry in odds_list:
				if len(top_attackers) >= 3:
					break	 
				if attacker_slot[entry['attacker']['id']] > 0:  # Ensure attacker can still be used
					if  defender['spies']>45:
						if entry['attacker']['spies']-defender['spies']>=0 and entry['optimal_attack']['odds']>70:
							attacker_id = entry['attacker']['id']
							entry['optimal_attack']['level'] = switcher.get(entry['optimal_attack']['level'])
							top_attackers.append(entry)
							attacker_slot[attacker_id] -= 1
					else:
						if	entry['optimal_attack']['odds']>70 or (entry['optimal_attack']['odds']>65 and defender['surveillance_network']):
							attacker_id = entry['attacker']['id']	
							entry['optimal_attack']['level'] = switcher.get(entry['optimal_attack']['level'])
							top_attackers.append(entry)
							attacker_slot[attacker_id] -= 1
			# Append results for this defender
			result.append({
				"defender": defender,
				"top_attackers": top_attackers
			})
	return result