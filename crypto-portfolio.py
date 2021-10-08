from binance.spot import Spot
import json
import csv
import os
from datetime import datetime
from decouple import config
from googleapiclient.discovery import build
from google.oauth2 import service_account
import requests

#Read config
filepath = os.path.dirname(os.path.realpath(__file__))
config = open(filepath + '/config.json')
data = json.load(config)
offline_assets = data['offline_assets']
target_allocations = data['target_allocations']
total_invested = data['total_invested']
DISCORD_WEBHOOK_URL = data['discord_webhook_url']
API_KEY = data['binance_api_key']
API_SECRET = data['binance_api_secret']
GOOGLE_SHEET_ID = data['google_sheet_id']
GOOGLE_SHEET_RANGE = data['google_sheet_range']

#Binance api
client = Spot(key=API_KEY, secret=API_SECRET)
account = client.account()
balances = account['balances']

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
overview = []
overview.append(['Investment', total_invested])
overview.append(['Current value', total_usd_value])
overview.append(['Percentage', total_usd_value / total_invested])
now = datetime.now()
overview.append(['Last updated at', now.strftime("%d/%m/%Y %H:%M:%S")])
overview.append([])
overview.append(['Asset',
                 'Price',
                 'Amount',
                 'USD Value',
                 'Target Alloc',
                 'Alloc',
                 'Alloc Diff',
                 'Amount Diff'])
overview = overview + assets

#Send discord notification if rebalancing is required
if notification_required:
    payload = {
        "username": "CryptoBot",
        "content": "Portfolio requires rebalancing"
    }
    response = requests.post(DISCORD_WEBHOOK_URL, json=payload)

#Write portfolio table to google sheet
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
credentials = None
gs_keys = filepath + '/crypto-portfolio-key.json'
credentials = service_account.Credentials.from_service_account_file(gs_keys,
                                                                    scopes=SCOPES)
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()
body = {
    'values': overview
}
request = sheet.values().update(spreadsheetId=GOOGLE_SHEET_ID,
                                range=GOOGLE_SHEET_RANGE,
                                valueInputOption='USER_ENTERED',
                                body=body).execute()
#Print goes to log
print()
print(now)
print(request)
