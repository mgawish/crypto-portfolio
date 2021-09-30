from binance.spot import Spot
import json
import csv
import os
from datetime import datetime
from decouple import config
from googleapiclient.discovery import build
from google.oauth2 import service_account
import requests

#Binance api
API_KEY = config('BINANCE_API_KEY')
API_SECRET = config('BINANCE_API_SECRET')
client = Spot(key=API_KEY, secret=API_SECRET)
account = client.account()
balances = account['balances']

#Read offline assets that are not on binance
filepath = os.path.dirname(os.path.realpath(__file__))
file = open(filepath + '/offline-assets.csv')
csvreader = csv.reader(file)
offline_assets = {}
for row in csvreader:
    offline_assets[row[0]] = float(row[1])

#Read target allocations
filepath = os.path.dirname(os.path.realpath(__file__))
file = open(filepath + '/target-allocations.csv')
csvreader = csv.reader(file)
target_allocations = {}
for row in csvreader:
    target_allocations[row[0]] = float(row[1])

#Generate portfolio rows
assets = []
total_usd_value = 0
alloc_total = 0
notification_required = False
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

    if target_allocations.get(asset) != None:
        alloc_total += usdValue

for i in range(len(assets)):
    a = assets[i]
    asset = a[0]
    price = a[1]
    amount = a[2]
    usd_value = price * amount
    alloc = usd_value / total_usd_value

    if target_allocations.get(asset) != None:
        target_alloc = target_allocations.get(asset)
        alloc_diff = target_alloc - alloc
        amount_change = (target_alloc * alloc_total - usd_value) / price
    else:
        target_allocation = 0
        alloc_diff = 0
        amount_change = 0

    if abs(alloc_diff) > target_alloc * 0.1:
        notification_required = True

    assets[i] = [asset,
                 price,
                 amount,
                 usd_value,
                 alloc,
                 target_alloc,
                 alloc_diff,
                 amount_change]

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

#Send discord notification if rebalancing is required
if notification_required:
    payload = {
        "username": "CryptoBot",
        "content": "Portfolio requires rebalancing"
    }
    response = requests.post(config('DISCORD_WEBHOOK_URL'), json=payload)

#Write portfolio table to google sheet
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = config('PORTFOLIO_SPREADSHEET_ID')
RANGE = config('PORTFOLIO_SHEET_RANGE')
credentials = None
gs_keys = filepath + '/crypto-portfolio-key.json'
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
