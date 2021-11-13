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
    config = json.load(open(filepath + '/config.json'))
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
        target_allocations = self.config['target_allocations']
        values = target_allocations.values()
        portfolio_alloc = round(sum(values), 2)

        if portfolio_alloc != 1:
            print(f'Allocation targets are equal to {portfolio_alloc}')
            return

        assets = self.fetch_bsc_balance()
        assets = self.fetch_binance_balance() + assets

        df = self.generate_df(assets)
        dff =  df[abs(df['alloc_diff']) > df['target_alloc'] * 0.1]
        if not dff.empty:
            self.send_notification()

        json_data = self.generate_overview(df)
        self.update_google_sheet(json_data)

    def fetch_binance_balance(self):
        api_key = self.config['binance_api_key']
        api_secret = self.config['binance_api_secret']
        client = Spot(key=api_key, secret=api_secret)
        account = client.account()
        balances = account['balances']
        offline_assets = self.config['offline_assets']
        target_allocations = self.config['target_allocations']
        assets = []

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

            if target_allocations.get(asset) != None:
                target_alloc = target_allocations.get(asset)
            else:
                target_alloc = 0

            value = amount * price
            assets.append({
                'asset': asset,
                'price': price,
                'amount': amount,
                'target_alloc': target_alloc
            })

        return assets

    def fetch_bsc_balance(self):
        wallet_address = self.config['wallet_address']
        api_key = self.config['bsc_api_key']
        contracts = self.config['wallet_contracts']
        assets = []
        for symbol in contracts:
            url = 'https://api.bscscan.com/api'
            params = {
                'module': 'account',
                'action': 'tokenbalance',
                'contractaddress': contracts[symbol],
                'address': wallet_address,
                'apiKey': api_key,
                'tag': 'latest'
            }

            response = requests.get(url, params=params)
            json_data = json.loads(response.text)
            amount = float(json_data['result']) * 10**-18
            price = self.fetch_cmc_price(symbol)

            assets.append({
                'asset': symbol,
                'price': price,
                'amount': amount,
                'target_alloc': 0
            })

        return assets

    def fetch_cmc_price(self, symbol):
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
        params = {
            'symbol': symbol
        }
        headers = {
            'X-CMC_PRO_API_KEY': self.config['cmc_api_key'],
            'Accept': 'application/json'
        }
        response = requests.get(url, params=params, headers=headers)
        json_data = json.loads(response.text)
        return json_data['data'][symbol]['quote']['USD']['price']

    def generate_df(self, assets):
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

        return df

    def generate_overview(self, df):
        total_invested = self.config['total_invested']
        overview = []
        overview.append(['Investment', total_invested])
        overview.append(['Current value', self.total_value])
        overview.append(['Percentage', self.total_value / total_invested])
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
        url = data['discord_webhook_url']
        payload = {
            "username": "CryptoBot",
            "content": "Portfolio requires rebalancing"
        }
        response = requests.post(url, json=payload)

    def update_google_sheet(self, data):
        sheet_name = self.config['google_sheet_name']
        sheet_id = self.config['google_sheet_id']
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        credentials = None
        gs_keys = self.filepath + '/crypto-portfolio-key.json'
        credentials = service_account.Credentials.from_service_account_file(gs_keys,
                                                                            scopes=SCOPES)
        service = build('sheets', 'v4', credentials=credentials)
        sheet = service.spreadsheets()

        #Clear sheet
        range = f'{sheet_name}!A1:Z'
        body = {}
        response = service.spreadsheets().values().clear(spreadsheetId=sheet_id,
                                                         range=range,
                                                         body=body).execute()
        #Update sheet
        range = f'{sheet_name}!A1'
        body = {
            'values': data
        }
        request = sheet.values().update(spreadsheetId=sheet_id,
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
