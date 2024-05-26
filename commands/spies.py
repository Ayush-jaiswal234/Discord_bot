from commands.scripts import sheets
import requests,sqlite3,threading,time

def sheet_creation(alliance_id):
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	alliance_name=('select alliance from all_nations_data where alliance_id=%s limit 1') % (alliance_id)
	cursor.execute(alliance_name)
	alliance_name=cursor.fetchone()
	cursor.close()
	connection.close()	
	sheetID=sheets.create(f'{alliance_name[0]} spies')
	thread=threading.Thread(target=sheet_data,args=(alliance_id,sheetID))
	thread.start()
	return sheetID
pass

def sheet_data(alliance_id,sheetID):
	query="""{
			nations(first:500,alliance_id:%s,vmode:false){
            data{
  				id
             	nation_name
              	score
            }
       }      
	}
	""" % (alliance_id)
	alliance_data=requests.get('https://api.politicsandwar.com/graphql?api_key=10433a4b8a7dec',json={'query':query})
	alliance_data=alliance_data.json()
	alliance_data=alliance_data['data']['nations']['data']
	time_start=time.time()
	spies_list=[spies_calculator(x['id']) for x in alliance_data]
	merged_list=[(f'=HYPERLINK("https://politicsandwar.com/nation/id={alliance_data[x]["id"]}","{alliance_data[x]["nation_name"]}")',f'{int(alliance_data[x]["score"]-(alliance_data[x]["score"]*0.6))}-{int(alliance_data[x]["score"]+(alliance_data[x]["score"]*1.50))}',spies_list[x]) for x in range(0,len(spies_list))]
	values=[
		['Nation','Spy range','Spies']
	]
	for x in range(0,len(merged_list)):
		values.insert(x+1,merged_list[x])
	time_end=time.time()	
	time_taken=[f'Finished execution in {int(time_end-time_start)} seconds']
	values.insert(len(merged_list)+2,time_taken)
	range_of_sheet=f'Sheet1!A1:C{len(alliance_data)+2}'
	sheets.write_ranges(sheetID,range_of_sheet,values)
pass

def spies_calculator(nation_id):
	fix_value,low,high=0,1,55
	m,found=26,False
	spies_data =requests.get(f'https://politicsandwar.com/war/espionage_get_odds.php?id1=209785&id2={nation_id}&id3=0&id4=1&id5=0')	
	if spies_data.text=='Greater than 50%':
		found=True
		fix_value=0
	spies_data =requests.get(f'https://politicsandwar.com/war/espionage_get_odds.php?id1=209785&id2={nation_id}&id3=0&id4=1&id5=55')	
	if spies_data.text=='Lower than 50%':
		found=True
		fix_value=55
	while found==False or m==55:
		spies_data =requests.get(f'https://politicsandwar.com/war/espionage_get_odds.php?id1=209785&id2={nation_id}&id3=0&id4=1&id5={m}')	
		if m==0 or m==54:
			found=True
			fix_value=m	
		elif spies_data.text=='Greater than 50%':
			high=m
			spies_data =requests.get(f'https://politicsandwar.com/war/espionage_get_odds.php?id1=209785&id2={nation_id}&id3=0&id4=1&id5={m-1}')	
			if spies_data.text=='Lower than 50%':
				found=True
				fix_value=m
		else:
			low=m
			spies_data =requests.get(f'https://politicsandwar.com/war/espionage_get_odds.php?id1=209785&id2={nation_id}&id3=0&id4=1&id5={m+1}')	
			if spies_data.text=='Greater than 50%':
				found=True
				fix_value=m+1					
		m=(low+high)//2			
	y=(4*fix_value-1)/3
	if y>60 or m==55:
		y=60
	elif y<0:
		y=0
	return int(y)
pass