from binance.spot import Spot
import json
import csv
import os
from datetime import datetime
from decouple import config
from googleapiclient.discovery import build
from google.oauth2 import service_account

#Binance api
API_KEY = config('BINANCE_API_KEY')
API_SECRET = config('BINANCE_API_SECRET')
client = Spot(key=API_KEY, secret=API_SECRET)
account = client.account()
balances = account['balances']

#Read offline assets that are not on binance
#If the asset does not exist on binance, it will be ignored
filepath = os.getcwd()
file = open(filepath + '/offline-assets.csv')
csvreader = csv.reader(file)
offline_assets = {}
for row in csvreader:
    offline_assets[row[0]] = float(row[1])

#Generate portfolio rows
assets = []
total_usd_value = 0
for b in balances:
    asset = b['asset']
    free = float(b['free'])
    locked = float(b['locked'])
    amount = free + locked

    if offline_assets.get(asset) != None:
        amount += offline_assets.get(asset)

    if amount == 0:
        continue

    if asset == 'USDT':
        price = 1
    else:
        price = float(client.ticker_price(f'{asset}USDT')['price'])

    usdValue = amount * price
    total_usd_value += usdValue
    assets.append([asset, price, amount])

for i in range(len(assets)):
    a = assets[i]
    usd_value = a[1] * a[2]
    alloc = usd_value / total_usd_value
    assets[i] = [a[0], a[1], a[2], usd_value, alloc]

#Add overview
file = open(filepath + '/investments.csv')
csvreader = csv.reader(file)
total_invested = 0
for row in csvreader:
    total_invested += float(row[0])
assets.append([])
assets.append(['Investment', total_invested])
assets.append(['Current value', total_usd_value])
assets.append(['Percentage', total_usd_value / total_invested])
now = datetime.now()
assets.append(['Last updated at', now.strftime("%d/%m/%Y %H:%M:%S")])

#Write portfolio table to google sheet
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = config('PORTFOLIO_SPREADSHEET_ID')
RANGE = 'Portfolio!A2'
credentials = None
gs_keys = 'crypto-portfolio-key.json'
credentials = service_account.Credentials.from_service_account_file(gs_keys,
                                                                    scopes=SCOPES)
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()
body = {
    'values': assets
}
request = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
                                range=RANGE,
                                valueInputOption='USER_ENTERED',
                                body=body).execute()
#Print goes to log
print()
print(now)
print(request)
