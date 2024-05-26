from datetime import datetime,timedelta
import sqlite3

def update_subscriptions(server_id,command_name,date_time):
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	days=date_time.find('d')
	hours=date_time.find('h')
	mins=date_time.find('m')
	if mins!=-1:
		mins=date_time[hours+1:mins]
	else:
	 	mins=0	
	if hours!=-1:
		hours=date_time[days+1:hours]
	else:
		hours=0	
	if days!=-1:
		days=date_time[:days]	
	else:
		days=0
	current_date=datetime.now().replace(microsecond=0)
	end_date=current_date+timedelta(days=int(days),hours=int(hours),minutes=int(mins))
	update_table="insert into subscriptions values(%s,'%s','%s') on conflict(server_id,command_name) do update set end_date='%s'" % (server_id,command_name,end_date,end_date)
	cursor.execute(update_table)
	connection.commit()
	cursor.close()
	connection.close()
pass

def check_subscriptions(server_id,command_name):
	connection=sqlite3.connect('politics and war.db')
	cursor=connection.cursor()
	search_subs=("select * from subscriptions where server_id=%s and command_name='%s'") %(server_id,command_name)
	cursor.execute(search_subs)
	validity=cursor.fetchone()
	cursor.close()
	connection.close()	
	return validity
pass