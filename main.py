from binance.spot import Spot
import json
import csv
import os
from datetime import datetime
from decouple import config
from googleapiclient.discovery import build
from google.oauth2 import service_account
import requests
import pandas as pd

#Read config
class Main():
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
    GOOGLE_SHEET_NAME = data['google_sheet_name']

    columns = ['asset',
               'price',
               'amount',
               'value',
               'alloc',
               'target_alloc',
               'alloc_diff',
               'amount_diff']
    total_value = 0
    total_alloc_value = 0
    notification_required = False

    def run_strategy(self):
        df = self.generate_assets()
        json_data = self.generate_overview(df)
        self.update_google_sheet(json_data)
        if self.notification_required:
            self.send_notification()

    def generate_assets(self):
        client = Spot(key=self.API_KEY, secret=self.API_SECRET)
        account = client.account()
        balances = account['balances']
        assets = []

        for b in balances:
            asset = b['asset']
            free = float(b['free'])
            locked = float(b['locked'])
            amount = free + locked

            if self.offline_assets.get(asset) != None:
                amount += self.offline_assets.get(asset)

            if amount == 0:
                continue

            if asset == 'USDT':
                price = 1
            else:
                price = float(client.ticker_price(f'{asset}USDT')['price'])

            if self.target_allocations.get(asset) != None:
                target_alloc = self.target_allocations.get(asset)
            else:
                target_alloc = 0

            value = amount * price
            assets.append({
                'asset': asset,
                'price': price,
                'amount': amount,
                'target_alloc': target_alloc
            })

        df = pd.DataFrame(data=assets, columns=self.columns)
        df['value'] = df['price'] * df['amount']
        self.total_value = df['value'].sum()

        alloc_portfolio = df.loc[df['target_alloc'] != 0]
        self.total_alloc_value = alloc_portfolio['value'].sum()

        df['alloc'] = 0
        df.loc[df['target_alloc'] != 0, 'alloc'] = df['value'] / self.total_alloc_value
        df['alloc_diff'] = df['target_alloc'] - df['alloc']

        df['amount_diff'] = 0
        df.loc[df['target_alloc'] != 0, 'amount_diff'] = (df['target_alloc'] * self.total_alloc_value - df['value']) / df['price']

        df = df.sort_values('value', ascending=False)

        dff =  df[abs(df['alloc_diff']) > df['target_alloc'] * 0.1]
        if not dff.empty:
            self.notification_required = True

        return df

    def generate_overview(self, df):
        overview = []
        overview.append(['Investment', self.total_invested])
        overview.append(['Current value', self.total_value])
        overview.append(['Percentage', self.total_value / self.total_invested])
        now = datetime.now()
        overview.append(['Last updated at', now.strftime("%d/%m/%Y %H:%M:%S")])
        overview.append([])

        cols = df.columns.tolist()
        cols = [str.capitalize() for str in cols]
        cols = [str.replace('_',' ') for str in cols]

        overview.append(cols)
        overview = overview + df.values.tolist()
        return overview

    def send_notification(self):
        print('send_notification')
        payload = {
            "username": "CryptoBot",
            "content": "Portfolio requires rebalancing"
        }
        response = requests.post(self.DISCORD_WEBHOOK_URL, json=payload)

    def update_google_sheet(self, data):
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        credentials = None
        gs_keys = self.filepath + '/crypto-portfolio-key.json'
        credentials = service_account.Credentials.from_service_account_file(gs_keys,
                                                                            scopes=SCOPES)
        service = build('sheets', 'v4', credentials=credentials)
        sheet = service.spreadsheets()

        #Clear sheet
        range = f'{self.GOOGLE_SHEET_NAME}!A1:Z'
        body = {}
        response = service.spreadsheets().values().clear(spreadsheetId=self.GOOGLE_SHEET_ID,
                                                         range=range,
                                                         body=body).execute()
        #Update sheet
        range = f'{self.GOOGLE_SHEET_NAME}!A1'
        body = {
            'values': data
        }
        request = sheet.values().update(spreadsheetId=self.GOOGLE_SHEET_ID,
                                        range=range,
                                        valueInputOption='USER_ENTERED',
                                        body=body).execute()
        #Print goes to log
        print()
        print(datetime.now())
        print(request)

if __name__ == '__main__':
    main = Main()
    main.run_strategy()
