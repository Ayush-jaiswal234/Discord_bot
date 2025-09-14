import sqlite3,requests
import pandas as pd
import re
from scripts.nation_data_converter import time_converter


async def get_slots_data(allies_data,enemies_data):
    query=''
    results=[]
    for rows in allies_data[['nation_id','nation']].itertuples():
        if len(query)<9900:
            query=f"""{query} {re.sub("[- 0-9]","_",rows[2])}:wars(defid:{rows[1]}){{data{{att_id}}}}"""
        else:
           query=f"{{ {query} }}"
           fetchdata=requests.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':query})
           results.append(fetchdata.json()['data'])
           query=''
           query=f"""{query} {re.sub("[- 0-9]","_",rows[2])}:wars(defid:{rows[1]}){{data{{att_id}}}}"""     
    query=f"{{ {query} }}"
    fetchdata=requests.post('https://api.politicsandwar.com/graphql?api_key=819fd85fdca0a686bfab',json={'query':query})
    results.append(fetchdata.json()['data'])
    
    fetchdata= {key:values for d in results for key,values in d.items()}
    values=[]
    connection=sqlite3.connect('pnw.db')
    cursor=connection.cursor()
    for index, row in allies_data.iterrows():
        nation_key=re.sub("[- 0-9]","_",row['nation'])
        if len(fetchdata[nation_key]['data']) != 0:
            i = 1
            for data in fetchdata[nation_key]['data']:
                attacker_data = enemies_data[enemies_data['nation_id'] == int(data['att_id'])]
                if not attacker_data.empty:
                    # Assuming attacker_data has only one row for the given nation_id
                    attacker_data = attacker_data.iloc[0]
                    # Using .at to update the original DataFrame
                    allies_data.at[index, f'soldiers_{i}'] = attacker_data['soldiers']
                    allies_data.at[index, f'tanks_{i}'] = attacker_data['tanks']
                    allies_data.at[index, f'aircraft_{i}'] = attacker_data['aircraft']
                    allies_data.at[index, f'ships_{i}'] = attacker_data['ships']         
                    
                else:    
                    attacker_data = cursor.execute(f'select soldiers,tanks,aircraft,ships from all_nations_data where nation_id={data["att_id"]}')

                    attacker_data = attacker_data.fetchone()
                    allies_data.at[index, f'soldiers_{i}'] = attacker_data[0]
                    allies_data.at[index, f'tanks_{i}'] = attacker_data[1]
                    allies_data.at[index, f'aircraft_{i}'] = attacker_data[2]
                    allies_data.at[index, f'ships_{i}'] = attacker_data[3] 
                i += 1    
        values.append(f'=HYPERLINK("https://politicsandwar.com/nation/id={row["nation_id"]}","{row["nation"]}")')
    connection.close()    
    allies_data.insert(0,column='nation_link',value=values)                 
    allies_data.drop(['nation_id','nation'],axis=1,inplace=True)
    allies_data.fillna('',inplace=True) 
    return allies_data                

async def war_vis_sheet(allies,enemies,spreadsheets,sheetID):
    search_params=['cities','score','offensive_wars','defensive_wars','soldiers','tanks','aircraft','ships']
    search_text = 'select nation_id,nation,alliance,cities,score,offensive_wars,defensive_wars,beige_turns,last_active,soldiers,tanks,aircraft,ships from all_nations_data where alliance_position>1 and alliance_id'
    if len(allies)==1:
        allies_search_text = f'{search_text} = {allies[0]}'
    else:
        allies_search_text = f'{search_text} in {allies}'	
    if len(enemies)==1:
        enemies_search_text = f'{search_text} = {enemies[0]}'
    else:
        enemies_search_text = f'{search_text} in {enemies}'	
    connection=sqlite3.connect('pnw.db')
    allies_data=pd.read_sql_query(allies_search_text,connection)
    allies_data['nation']=allies_data['nation'].apply(lambda x: x.strip("'"))
    enemies_data=pd.read_sql_query(enemies_search_text,connection)
    enemies_data['nation']=enemies_data['nation'].apply(lambda x: x.strip("'"))
    connection.close()
    len_allies,len_enemies=	len(allies_data),len(enemies_data)
    values=[('Category','Allies','Enemies','Difference')]
    values.append(('Nation',len_allies,len_enemies,len_allies-len_enemies))
    for x in search_params:
            if not 'wars' in x:
                values.append((x,sum(allies_data[x]),sum(enemies_data[x]),sum(allies_data[x])-sum(enemies_data[x])))
            values.append((f'Average {x}',sum(allies_data[x])/len_allies,sum(enemies_data[x])/len_enemies,sum(allies_data[x])/len_allies-sum(enemies_data[x])/len_enemies))
    range_of_sheet=f'Overview!A1:D16'
    spreadsheets.write_ranges(sheetID,range_of_sheet,values)
    updated_allies=await get_slots_data(allies_data.copy(),enemies_data.copy())
    updated_allies['last_active'] = pd.to_datetime(updated_allies['last_active'],format="%Y-%m-%d %H:%M:%S")
    updated_allies['last_active'] = updated_allies['last_active'].apply(time_converter,args=(False,))

    updated_enemies=await get_slots_data(enemies_data,allies_data)
    updated_enemies['last_active'] = pd.to_datetime(updated_enemies['last_active'],format="%Y-%m-%d %H:%M:%S")
    updated_enemies['last_active'] = updated_enemies['last_active'].apply(time_converter,args=(False,))

    updated_allies_values = list(updated_allies.itertuples(index=False))
    updated_allies_values.insert(0,tuple(updated_allies.columns))
    

    updated_enemies_values = list(updated_enemies.itertuples(index=False))
    updated_enemies_values.insert(0,tuple(updated_enemies.columns))
    

    spreadsheets.write_ranges(sheetID,f'Allies!A1:X{len(updated_allies_values)}',updated_allies_values)
    spreadsheets.write_ranges(sheetID,f'Enemies!A1:X{len(updated_enemies_values)}',updated_enemies_values)
    rules=[]
    rules_dict_list=[{"startColumnIndex": 0,"endColumnIndex": 24,"userEnteredValue": "=$G2<>0","backgroundColor": {"red": 252/255,"green": 186/255,"blue": 3/255}},
    {"startColumnIndex": 8,"endColumnIndex": 9,"userEnteredValue":"=LTE(I2,C2*15000*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 8,"endColumnIndex": 9,"userEnteredValue":"=AND(GT(I2,C2*15000*0.20),LTE(I2,C2*15000*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 8,"endColumnIndex": 9,"userEnteredValue":"=AND(GT(I2,C2*15000*0.40),LTE(I2,C2*15000*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 8,"endColumnIndex": 9,"userEnteredValue":"=AND(GT(I2,C2*15000*0.60),LTE(I2,C2*15000*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 8,"endColumnIndex": 9,"userEnteredValue":"=GT(I2,C2*15000*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 9,"endColumnIndex": 10,"userEnteredValue":"=LTE(J2,C2*1250*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 9,"endColumnIndex": 10,"userEnteredValue":"=AND(GT(J2,C2*1250*0.20),LTE(J2,C2*1250*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 9,"endColumnIndex": 10,"userEnteredValue":"=AND(GT(J2,C2*1250*0.40),LTE(J2,C2*1250*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 9,"endColumnIndex": 10,"userEnteredValue":"=AND(GT(J2,C2*1250*0.60),LTE(J2,C2*1250*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 9,"endColumnIndex": 10,"userEnteredValue":"=GT(J2,C2*1250*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 10,"endColumnIndex": 11,"userEnteredValue":"=LTE(K2,C2*75*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 10,"endColumnIndex": 11,"userEnteredValue":"=AND(GT(K2,C2*75*0.20),LTE(K2,C2*75*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 10,"endColumnIndex": 11,"userEnteredValue":"=AND(GT(K2,C2*75*0.40),LTE(K2,C2*75*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 10,"endColumnIndex": 11,"userEnteredValue":"=AND(GT(K2,C2*75*0.60),LTE(K2,C2*75*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 10,"endColumnIndex": 11,"userEnteredValue":"=GT(K2,C2*75*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 11,"endColumnIndex": 12,"userEnteredValue":"=LTE(L2,C2*15*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 11,"endColumnIndex": 12,"userEnteredValue":"=AND(GT(L2,C2*15*0.20),LTE(L2,C2*15*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 11,"endColumnIndex": 12,"userEnteredValue":"=AND(GT(L2,C2*15*0.40),LTE(L2,C2*15*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 11,"endColumnIndex": 12,"userEnteredValue":"=AND(GT(L2,C2*15*0.60),LTE(L2,C2*15*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 11,"endColumnIndex": 12,"userEnteredValue":"=GT(L2,C2*15*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 12,"endColumnIndex": 13,"userEnteredValue":"=LTE(M2,I2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 12,"endColumnIndex": 13,"userEnteredValue":"=AND(GT(M2,I2*0.20),LTE(M2,I2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 12,"endColumnIndex": 13,"userEnteredValue":"=AND(GT(M2,I2*0.40),LTE(M2,I2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 12,"endColumnIndex": 13,"userEnteredValue":"=AND(GT(M2,I2*0.60),LTE(M2,I2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 12,"endColumnIndex": 13,"userEnteredValue":"=GT(M2,I2*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 13,"endColumnIndex": 14,"userEnteredValue":"=LTE(N2,J2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 13,"endColumnIndex": 14,"userEnteredValue":"=AND(GT(N2,J2*0.20),LTE(N2,J2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 13,"endColumnIndex": 14,"userEnteredValue":"=AND(GT(N2,J2*0.40),LTE(N2,J2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 13,"endColumnIndex": 14,"userEnteredValue":"=AND(GT(N2,J2*0.60),LTE(N2,J2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 13,"endColumnIndex": 14,"userEnteredValue":"=GT(N2,J2*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 14,"endColumnIndex": 15,"userEnteredValue":"=LTE(O2,K2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 14,"endColumnIndex": 15,"userEnteredValue":"=AND(GT(O2,K2*0.20),LTE(O2,K2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 14,"endColumnIndex": 15,"userEnteredValue":"=AND(GT(O2,K2*0.40),LTE(O2,K2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 14,"endColumnIndex": 15,"userEnteredValue":"=AND(GT(O2,K2*0.60),LTE(O2,K2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 14,"endColumnIndex": 15,"userEnteredValue":"=GT(O2,K2*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 15,"endColumnIndex": 16,"userEnteredValue":"=LTE(P2,L2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 15,"endColumnIndex": 16,"userEnteredValue":"=AND(GT(P2,L2*0.20),LTE(P2,L2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 15,"endColumnIndex": 16,"userEnteredValue":"=AND(GT(P2,L2*0.40),LTE(P2,L2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 15,"endColumnIndex": 16,"userEnteredValue":"=AND(GT(P2,L2*0.60),LTE(P2,L2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 15,"endColumnIndex": 16,"userEnteredValue":"=GT(P2,L2*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 16,"endColumnIndex": 17,"userEnteredValue":"=LTE(Q2,I2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 16,"endColumnIndex": 17,"userEnteredValue":"=AND(GT(Q2,I2*0.20),LTE(Q2,I2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 16,"endColumnIndex": 17,"userEnteredValue":"=AND(GT(Q2,I2*0.40),LTE(Q2,I2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 16,"endColumnIndex": 17,"userEnteredValue":"=AND(GT(Q2,I2*0.60),LTE(Q2,I2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 16,"endColumnIndex": 17,"userEnteredValue":"=GT(Q2,I2*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 17,"endColumnIndex": 18,"userEnteredValue":"=LTE(R2,J2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 17,"endColumnIndex": 18,"userEnteredValue":"=AND(GT(R2,J2*0.20),LTE(R2,J2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 17,"endColumnIndex": 18,"userEnteredValue":"=AND(GT(R2,J2*0.40),LTE(R2,J2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 17,"endColumnIndex": 18,"userEnteredValue":"=AND(GT(R2,J2*0.60),LTE(R2,J2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 17,"endColumnIndex": 18,"userEnteredValue":"=GT(R2,J2*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 18,"endColumnIndex": 19,"userEnteredValue":"=LTE(S2,K2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 18,"endColumnIndex": 19,"userEnteredValue":"=AND(GT(S2,K2*0.20),LTE(S2,K2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 18,"endColumnIndex": 19,"userEnteredValue":"=AND(GT(S2,K2*0.40),LTE(S2,K2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 18,"endColumnIndex": 19,"userEnteredValue":"=AND(GT(S2,K2*0.60),LTE(S2,K2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 18,"endColumnIndex": 19,"userEnteredValue":"=GT(S2,K2*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 19,"endColumnIndex": 20,"userEnteredValue":"=LTE(T2,L2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 19,"endColumnIndex": 20,"userEnteredValue":"=AND(GT(T2,L2*0.20),LTE(T2,L2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 19,"endColumnIndex": 20,"userEnteredValue":"=AND(GT(T2,L2*0.40),LTE(T2,L2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 19,"endColumnIndex": 20,"userEnteredValue":"=AND(GT(T2,L2*0.60),LTE(T2,L2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 19,"endColumnIndex": 20,"userEnteredValue":"=GT(T2,L2*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 20,"endColumnIndex": 21,"userEnteredValue":"=LTE(U2,I2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 20,"endColumnIndex": 21,"userEnteredValue":"=AND(GT(U2,I2*0.20),LTE(U2,I2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 20,"endColumnIndex": 21,"userEnteredValue":"=AND(GT(U2,I2*0.40),LTE(U2,I2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 20,"endColumnIndex": 21,"userEnteredValue":"=AND(GT(U2,I2*0.60),LTE(U2,I2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 20,"endColumnIndex": 21,"userEnteredValue":"=GT(U2,I2*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 21,"endColumnIndex": 22,"userEnteredValue":"=LTE(V2,J2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 21,"endColumnIndex": 22,"userEnteredValue":"=AND(GT(V2,J2*0.20),LTE(V2,J2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 21,"endColumnIndex": 22,"userEnteredValue":"=AND(GT(V2,J2*0.40),LTE(V2,J2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 21,"endColumnIndex": 22,"userEnteredValue":"=AND(GT(V2,J2*0.60),LTE(V2,J2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 21,"endColumnIndex": 22,"userEnteredValue":"=GT(V2,J2*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 22,"endColumnIndex": 23,"userEnteredValue":"=LTE(W2,K2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 22,"endColumnIndex": 23,"userEnteredValue":"=AND(GT(W2,K2*0.20),LTE(W2,K2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 22,"endColumnIndex": 23,"userEnteredValue":"=AND(GT(W2,K2*0.40),LTE(W2,K2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 22,"endColumnIndex": 23,"userEnteredValue":"=AND(GT(W2,K2*0.60),LTE(W2,K2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 22,"endColumnIndex": 23,"userEnteredValue":"=GT(W2,K2*0.80)","backgroundColor":{"red": 1}},

    {"startColumnIndex": 23,"endColumnIndex": 24,"userEnteredValue":"=LTE(X2,L2*0.2)","backgroundColor":{"green":1}},
    {"startColumnIndex": 23,"endColumnIndex": 24,"userEnteredValue":"=AND(GT(X2,L2*0.20),LTE(X2,L2*0.4))","backgroundColor":{"red": 46/255,"green": 139/255,"blue": 87/255}},
    {"startColumnIndex": 23,"endColumnIndex": 24,"userEnteredValue":"=AND(GT(X2,L2*0.40),LTE(X2,L2*0.6))","backgroundColor":{"red": 1,"green": 1}},
    {"startColumnIndex": 23,"endColumnIndex": 24,"userEnteredValue":"=AND(GT(X2,L2*0.60),LTE(X2,L2*0.8))","backgroundColor":{"red": 1,"green": 165/255}},
    {"startColumnIndex": 23,"endColumnIndex": 24,"userEnteredValue":"=GT(X2,L2*0.80)","backgroundColor":{"red": 1}},
    ]


    gradient_rule=[{"startColumnIndex": 4,"endColumnIndex": 5},{"startColumnIndex": 5,"endColumnIndex": 6}]
    border_rule=[{"startColumnIndex": 12,"endColumnIndex": 13},{"startColumnIndex": 16,"endColumnIndex": 17},{"startColumnIndex": 20,"endColumnIndex": 21},
    {"startColumnIndex": 24,"endColumnIndex": 25}]

    for sheets in [(1,len(updated_allies_values)),(2,len(updated_enemies_values))]:
        for rules_dict in rules_dict_list:
            rule={
            "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [
                            {
                                "sheetId": sheets[0],  
                                "startRowIndex": 1,
                                "endRowIndex": sheets[1], 
                                "startColumnIndex": rules_dict['startColumnIndex'],
                                "endColumnIndex": rules_dict['endColumnIndex']
                            }
                        ],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [
                                    {
                                        "userEnteredValue": rules_dict['userEnteredValue']
                                    }
                                ]
                            },
                            "format": {
                                "backgroundColor": rules_dict['backgroundColor']
                            }
                        }
                    },
                    "index": 0
                }
            }
            rules.append(rule)

        for rules_dict in gradient_rule:
            rule={
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [
                            {
                                "sheetId": sheets[0],
                                "startRowIndex": 1,
                                "endRowIndex": sheets[1], 
                                "startColumnIndex": rules_dict['startColumnIndex'],
                                "endColumnIndex": rules_dict['endColumnIndex']
                            }
                        ],
                        "gradientRule": {
                            "minpoint": {
                                "colorStyle": {
                                    "rgbColor":{
                                        "green": 1}
                                },
                                "type": "MIN"
                            },
                            "midpoint": {
                                "colorStyle": {
                                    "rgbColor":{
                                        "red": 1,
                                        "green": 165/255}
                                },
                                "type": "PERCENTILE",
                                "value":"67"
                            },
                            "maxpoint": {
                                "colorStyle": {
                                    "rgbColor":{
                                        "red": 1}
                                },
                                "type": "MAX"
                            },
                        }
                    },
                    "index": 0
                }
            }   
            rules.append(rule) 

        for rules_dict in border_rule:
            rule={
                "updateBorders": {
                "range": {
                    "sheetId": sheets[0],
                    "startRowIndex": 0,
                    "endRowIndex": sheets[1],
                    "startColumnIndex": rules_dict['startColumnIndex'],
                    "endColumnIndex": rules_dict['endColumnIndex']
                    },
                "left":{
                    "style":"SOLID_MEDIUM"
                }    
                }
            }
            rules.append(rule)

        rule=  {
        "autoResizeDimensions": {
            "dimensions": {
            "sheetId": sheets[0],
            "dimension": "COLUMNS",
            "startIndex": 2,
            "endIndex": 24
            }
        }
        }
        rules.append(rule)   


    spreadsheets.conditional_formatting(sheetID,rules)


		
      	