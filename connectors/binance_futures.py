#%%
import logging
import requests
import pprint
import time
# import typing #used python3.9 notation instead

import hmac
import hashlib
from urllib.parse import urlencode

import websocket  #pip install "websocket-client"
import json

import threading

from models import *  # own data types


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
    def __init__(self, public_key: str, secret_key: str, testnet: bool):
        if testnet:
            self._base_url = "https://testnet.binancefuture.com"
            self._wss_url = "wss://stream.binancefuture.com/ws"
        else:
            self._base_url = "https://fapi.binance.com"
            self._wss_url = "wss://fstream.binance.com/ws"

        self._public_key = public_key
        self._secret_key = secret_key

        self._headers = {'X-MBX-APIKEY': self._public_key}

        self.contracts = self.get_contracts()
        self.balances = self.get_balances()

        self.prices = dict()

        self._ws_id = 1
        self._ws = None

        # since ws.run_forver() runs an infinite loop, everything below that line wouldn't execute
        # solution: run it in a thread, i.e. in a parallel background task.
        t = threading.Thread(target=self._start_ws)
        # self.start_ws() <-- alone wouldnt work
        t.start()

        logger.info("Binance Futures Client sucessfully initialized")

    def _generate_signature(self, data: dict) -> str: #check if generic dict works, maybe "typing.Dict" needed that allows more complex variables in it
        #encode() turns strings into byte-objects (as expected by hmac)
        return hmac.new(self._secret_key.encode(), urlencode(data).encode(), hashlib.sha256).hexdigest()
        #to see what urlencode does: https://linuxhint.com/urlencode-python/

    def _make_request(self, method: str, endpoint: str, data: dict):
        if method == "GET":
            try:
                response = requests.get(self._base_url + endpoint, params=data, headers=self._headers)
            except Exception as e:
                logger.error(f"Connection error while making {method} request to {endpoint}: {e}")
                return None  # because we won't even have a response.status_code
        elif method == "POST":
            try:
                response = requests.post(self._base_url + endpoint, params=data, headers=self._headers)
            except Exception as e:
                logger.error(f"Connection error while making {method} request to {endpoint}: {e}")
                return None
        elif method == "DELETE":
            try:
                response = requests.delete(self._base_url + endpoint, params=data, headers=self._headers)
            except Exception as e:
                logger.error(f"Connection error while making {method} request to {endpoint}: {e}")
                return None
        else:
            raise ValueError()

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f'''Error while making {method} request to {endpoint}:
                         {response.json()} (error code {response.status_code}''')
            return None

    def get_contracts(self) -> dict[str, Contract]:
        exchange_info = self._make_request("GET", "/fapi/v1/exchangeInfo", dict())  # we send dict() empty dict, instead of None, because make_request() type hinting expects dict now.

        contracts = dict()
        if exchange_info is not None:
            for contract_data in exchange_info['symbols']:
                # contracts[contract_data['pair']] = contract_data  # would return a dictionary type
                contracts[contract_data['pair']] = Contract(contract_data) # see models.py

        return contracts

    def get_historical_candles(self, contract: Contract, interval: str) -> list:
        data = dict()
        data['symbol'] = contract.symbol
        data['interval'] = interval
        data['limit'] = 1000

        raw_candles = self._make_request("GET", "/fapi/v1/klines", data)

        candles = []

        if raw_candles is not None:
            for c in raw_candles:
                # by checking the documentation https://binance-docs.github.io/apidocs/futures/en/#kline-candlestick-data
                # one sees example response: a list of values open time, open, high, low, close, volume
                # candles.append([c[0], float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])])
                # replaced in Lesson 15:
                candles.append(Candle(c, interval, 'binance'))
    
        return candles
    
    def get_bid_ask(self, contract: Contract) -> dict[str, float]:
        # if we had multiple parameters: URL?symbol=XX&param1=XY&param2=ZZ
        # but to make life easier, request method can take argument "parameters" as dict.
        #"https://testnet.binancefuture.com/fapi/v1/ticker/bookTicker?symbol=BTCUSDT&key"
        data = dict()
        data['symbol'] = contract.symbol
        ob_data = self._make_request("GET", "/fapi/v1/ticker/bookTicker", data)

        if ob_data is not None:
            bid_data = float(ob_data['bidPrice'])
            ask_data = float(ob_data['askPrice'])
            if contract.symbol not in self.prices:
                # see binance documentation about the keys that are returned
                self.prices[contract.symbol] = {'bid': bid_data, 'ask': ask_data}
            else:
                self.prices[contract.symbol]['bid'] = bid_data
                self.prices[contract.symbol]['ask'] = ask_data

            return self.prices[contract.symbol]

    def get_balances(self) -> dict[str, Balance]:
        data = dict()
        data['timestamp'] = int(time.time()*1000)
        data['signature'] = self._generate_signature(data)

        balances = dict()
        # see https://binance-docs.github.io/apidocs/futures/en/#account-information-v2-user_data
        # for input (data is empty, except timestamp in signature) and response example
        account_data = self._make_request("GET", "/fapi/v1/account", data)

        if account_data is not None:
            for a in account_data['assets']:
                balances[a['asset']] = Balance(a)  #instead of just using "a" (dictionary object), we now turn it into a Balance object (specified in models.py)
        # print('testing output: ', balances['USDT'].wallet_balance)

        return balances

    def place_order(self, contract: Contract, side: str, quantity: float, order_type: str, price=None, tif=None) -> OrderStatus:
        #endpoint info: https://binance-docs.github.io/apidocs/futures/en/#new-order-trade
        data = dict()
        data['symbol'] = contract.symbol
        data['side'] = side   #could be BUY SELL
        data['quantity'] = round(quantity / contract.lot_size) * contract.lot_size #order quant is integer, last round not needed
        data['type'] = order_type  # LIMIT  or others

        if price is not None:
            data['price'] = round(round(price / contract.tick_size) * contract.tick_size, 8)
        if tif is not None:
            data['timeInForce'] = tif

        data['timestamp'] = int(time.time()*1000)
        data['signature'] = self._generate_signature(data)

        order_status = self._make_request('POST', '/fapi/v1/order', data)
        if order_status is not None:
            order_status = OrderStatus(order_status, 'binance')

        return order_status

    def cancel_order(self, contract: Contract, orderId: int) -> OrderStatus:
        
        data = dict()
        data['orderId'] = orderId
        data['symbol'] = contract.symbol

        data['timestamp'] = int(time.time()*1000)
        data['signature'] = self._generate_signature(data)

        order_status = self._make_request('DELETE', '/fapi/v1/order', data)

        if order_status is not None:
            order_status = OrderStatus(order_status, 'binance')

        return order_status

    def get_order_status(self, contract: Contract, order_id: int) -> OrderStatus:

        data = dict()
        data['timestamp'] = int(time.time() * 1000)
        data['symbol'] = contract.symbol
        data['orderId'] = order_id
        data['signature'] = self._generate_signature(data)

        order_status = self._make_request("GET", "/fapi/v1/order", data)

        return order_status


    def _start_ws(self):
        # websocket connection using websocket-client module
        self._ws = websocket.WebSocketApp(self._wss_url, on_open=self._on_open, on_close=self._on_close,
        on_error=self._on_error, on_message=self._on_message)  # declared as instance variable, since we use it across many methods

        while True:  # By putting run_forever() in infinite while loop, it will restart if connection is interrupted.
                     # Because any websocket error will trigger except statement, after which code continues
            try:
                self._ws.run_forever()  # check above under __init__ how to deal with this infinite loop problem in python
            except Exception as e:
                logger.error("Binance error in run_forever() method: {e}")
            time.sleep(2) # if connection cannot be restarted immediately, prevents continuously trying
    
    # below functions that are called "callback functions"
    def _on_open(self):  #some versions may need "ws" as input argument here
        logger.info("Binance connection opened")

        self.subscribe_channel(list(self.contracts.values()), 'bookTicker')  #not sure why its contracts.values here and not keys...

    def _on_close(self):
        logger.warning("Binance websocket connection closed")

    def _on_error(self, msg: str):
        logger.error(f"Binance connection error: {msg}")

    def _on_message(self, msg: str):
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
                
                # print(self.prices[symbol])

    def subscribe_channel(self, contracts: list[Contract], channel: str):
        #https://binance-docs.github.io/apidocs/spot/en/#live-subscribing-unsubscribing-to-streams
        # expects a json object, i.e. in python we create a dict with expected parameters
        data = dict()
        data['method'] = "SUBSCRIBE"
        data['params'] = []

        for contract in contracts:
            data['params'].append(contract.symbol.lower() + "@" + channel)  # e.g. channel "btcusdt@bookTicker" must be lowercase symbols
        data['id'] = self._ws_id

        # print(data, type(data))
        # print(json.dumps(data), type(json.dumps(data))) # looks the same, but dumps() turns it into json string
        try:
            self._ws.send(json.dumps(data)) #send method expects string, not dict
        except Exception as e:
            logger.error(f"Websocket error while subscribing to {len(contracts)} {channel} updates: {e}")

        self._ws_id += 1  # instance variable from init, increase for every subscription
