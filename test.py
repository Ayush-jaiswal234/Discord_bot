import asyncio
import datetime
import aiosqlite
from commands.scripts.updater import update_nation_data
from commands.scripts import sheets
import httpx
import time
import numpy as np

async def test():
    score= 5689.50
    war_range = score*0.75,score*2.5
    
    print(f'https://docs.google.com/spreadsheets/d/{sheetID}')        

asyncio.run(test())