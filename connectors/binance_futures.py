#%%
import logging
import requests
import pprint
import time

import hmac
import hashlib
from urllib.parse import urlencode

import websocket  #pip install "websocket-client"
import json

import threading

#%%
logger = logging.getLogger()

# test code below was deleted in course because we create a class instead
# terminology: fapi.binance.com is the base url, fapi/v1/exchangeInfo is the endpoint

# def get_contracts():
#     response_object = requests.get('https://fapi.binance.com/fapi/v1/exchangeInfo')
#     print(response_object.status_code)
#     # pprint.pprint(response_object.json())

#     # pprint.pprint(response_object.json()['symbols'])

#     contracts = []

#     for contract in response_object.json()['symbols']:
#         # pprint.pprint(contract)
#         # print(contract['pair'])
#         contracts.append(contract['pair'])

#     return contracts

# print(get_contracts())


class BinanceFuturesClient:
    def __init__(self, public_key, secret_key, testnet):
        if testnet:
            self.base_url = "https://testnet.binancefuture.com"
            self.wss_url = "wss://stream.binancefuture.com/ws"
        else:
            self.base_url = "https://fapi.binance.com"
            self.wss_url = "wss://fstream.binance.com/ws"

        self.public_key = public_key
        self.secret_key = secret_key

        self.headers = {'X-MBX-APIKEY': self.public_key}

        self.prices = dict()

        self.id = 1

        # since ws.run_forver() runs an infinite loop, everything below that line wouldn't execute
        # solution: run it in a thread, i.e. in a parallel background task.
        t = threading.Thread(target=self.start_ws)
        # self.start_ws() <-- alone wouldnt work
        t.start()

        logger.info("Binance Futures Client sucessfully initialized")

    def generate_signature(self, data):
        #encode() turns strings into byte-objects (as expected by hmac)
        return hmac.new(self.secret_key.encode(), urlencode(data).encode(), hashlib.sha256).hexdigest()

    def make_request(self, method, endpoint, data):
        if method == "GET":
            response = requests.get(self.base_url + endpoint, params=data, headers=self.headers)
        elif method == "POST":
            response = requests.post(self.base_url + endpoint, params=data, headers=self.headers)
        elif method == "DELETE":
            response = requests.delete(self.base_url + endpoint, params=data, headers=self.headers)
        else:
            raise ValueError()

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f'''Error while making {method} request to {endpoint}:
                         {response.json()} (error code {response.status_code}''')
            return None

    def get_contracts(self):
        exchange_info = self.make_request("GET", "/fapi/v1/exchangeInfo", None)

        contracts = dict()
        if exchange_info is not None:
            for contract_data in exchange_info['symbols']:
                contracts[contract_data['pair']] = contract_data

        return contracts

    def get_historical_candles(self, symbol, interval):
        data = dict()
        data['symbol'] = symbol
        data['interval'] = interval
        data['limit'] = 1000

        raw_candles = self.make_request("GET", "/fapi/v1/klines", data)

        candles = []

        if raw_candles is not None:
            for c in raw_candles:
                # by checking the documentation https://binance-docs.github.io/apidocs/futures/en/#kline-candlestick-data
                # one sees example response: a list of values open time, open, high, low, close, volume
                candles.append([c[0], float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])])
    
        return candles
    
    def get_bid_ask(self, symbol):
        # if we had multiple parameters: URL?symbol=XX&param1=XY&param2=ZZ
        # but to make life easier, request method can take argument "parameters" as dict.
        #"https://testnet.binancefuture.com/fapi/v1/ticker/bookTicker?symbol=BTCUSDT&key"
        data = dict()
        data['symbol'] = symbol
        ob_data = self.make_request("GET", "/fapi/v1/ticker/bookTicker", data)

        if ob_data is not None:
            bid_data = float(ob_data['bidPrice'])
            ask_data = float(ob_data['askPrice'])
            if symbol not in self.prices:
                # see binance documentation about the keys that are returned
                self.prices[symbol] = {'bid': bid_data, 'ask': ask_data}
            else:
                self.prices[symbol]['bid'] = bid_data
                self.prices[symbol]['ask'] = ask_data

        return self.prices[symbol]

    def get_balances(self):
        data = dict()
        data['timestamp'] = int(time.time()*1000)
        data['signature'] = self.generate_signature(data)

        balances = dict()
        # see https://binance-docs.github.io/apidocs/futures/en/#account-information-v2-user_data
        # for input (data is empty, except timestamp in signature) and response example
        account_data = self.make_request("GET", "/fapi/v1/account", data)

        if account_data is not None:
            for a in account_data['assets']:
                balances[a['asset']] = a

        return balances

    def place_order(self, symbol, side, quantity, order_type, price=None, tif=None):
        #endpoint info: https://binance-docs.github.io/apidocs/futures/en/#new-order-trade
        data = dict()
        data['symbol'] = symbol
        data['side'] = side   #could be BUY SELL
        data['quantity'] = quantity
        data['type'] = order_type  # LIMIT  or others

        if price is not None:
            data['price'] = price
        if tif is not None:
            data['timeInForce'] = tif

        data['timestamp'] = int(time.time()*1000)
        data['signature'] = self.generate_signature(data)

        order_status = self.make_request('POST', '/fapi/v1/order', data)

        return order_status

    def cancel_order(self, symbol, orderId):
        
        data = dict()
        data['orderId'] = orderId
        data['symbol'] = symbol

        data['timestamp'] = int(time.time()*1000)
        data['signature'] = self.generate_signature(data)

        order_status = self.make_request('DELETE', '/fapi/v1/order', data)

        return order_status

    def get_order_status(self, symbol, order_id):

        data = dict()
        data['timestamp'] = int(time.time() * 1000)
        data['symbol'] = symbol
        data['orderId'] = order_id
        data['signature'] = self.generate_signature(data)

        order_status = self.make_request("GET", "/fapi/v1/order", data)

        return order_status


    def start_ws(self):
        # websocket connection using websocket-client module
        self.ws = websocket.WebSocketApp(self.wss_url, on_open=self.on_open, on_close=self.on_close,
        on_error=self.on_error, on_message=self.on_message)  # declared as instance variable, since we use it across many methods
        self.ws.run_forever()  # check above under __init__ how to deal with this infinite loop problem in python

    # below functions that are called "callback functions"
    def on_open(self):  #some versions may need "ws" as input argument here
        logger.info("Binance connection opened")

        self.subscribe_channel("BTCUSDT")

    def on_close(self):
        logger.warning("Binance websocket connection closed")

    def on_error(self, msg):
        logger.error(f"Binance connection error: {msg}")

    def on_message(self, msg):
        # print(msg)
        # example response is a dict:
        # {"e":"bookTicker","u":22437778066,"s":"BTCUSDT","b":"47229.85","B":"54.585","a":"47232.81","A":"65.202","T":1633092536099,"E":1633092536102}
        # e=event type,  s=symbol (see https://binance-docs.github.io/apidocs/spot/en/#live-subscribing-unsubscribing-to-streams)
        # b/a=bid/ask

        data = json.loads(msg) # does the opposite of dumps() turns it into dict

        # create a clean feed of only bid and ask prices for the given symbol:
        if "e" in data:
            if data['e'] == "bookTicker":

                symbol = data['s']

                # part below adapted from get_bid_ask() function
                bid_data = float(data['b'])
                ask_data = float(data['a'])
                if symbol not in self.prices:
                    self.prices[symbol] = {'bid': bid_data, 'ask': ask_data}
                else:
                    self.prices[symbol]['bid'] = bid_data
                    self.prices[symbol]['ask'] = ask_data
                
                print(self.prices[symbol])

    def subscribe_channel(self, symbol):
        #https://binance-docs.github.io/apidocs/spot/en/#live-subscribing-unsubscribing-to-streams
        # expects a json object, i.e. in python we create a dict with expected parameters
        data = dict()
        data['method'] = "SUBSCRIBE"
        data['params'] = []
        data['params'].append(symbol.lower() + "@bookTicker")  # e.g. channel "btcusdt@bookTicker" must be lowercase symbols
        data['id'] = self.id

        # print(data, type(data))
        # print(json.dumps(data), type(json.dumps(data))) # looks the same, but dumps() turns it into json string

        self.ws.send(json.dumps(data)) #send method expects string, not dict


        self.id += 1  # instance variable from init, increase for every subscription
