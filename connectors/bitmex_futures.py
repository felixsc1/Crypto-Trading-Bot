#%%
import logging
import requests
import time

import hmac
import hashlib
import urllib.parse
from urllib.parse import urlencode

import websocket
import json
import threading

from models import *

logger = logging.getLogger()

'''
important links:
https://testnet.bitmex.com/app/apiOverview
https://www.bitmex.com/app/apiOverview
to get started:
interactive: https://www.bitmex.com/api/explorer/

testnet account under my protonmail
'''

#%%
# logger = logging.getLogger()

class BitmexFuturesClient:

    def __init__(self, public_key: str, secret_key: str, testnet: bool):
        if testnet:
            self._base_url = 'https://testnet.bitmex.com/api/v1'
            self._wss_url = 'wss://testnet.bitmex.com/realtime'
        else:
            self._base_url = 'https://www.bitmex.com/api/v1'
            self._wss_url = 'wss://www.bitmex.com/realtime'

        self._public_key = public_key
        self._secret_key = secret_key

        self.contracts = self.get_contracts()
        self.balances = self.get_balances()

        self.prices = dict()

        self._ws = None
        self._ws_id = 1

        # t = threading.Thread(target=self._start_ws)
        # t.start()

        logger.info("Bitmex Client successfully initialized")


     
    def _add_headers(self, method, endpoint, data) -> str:
        '''
        Way more complex than that of binance
        https://testnet.bitmex.com/app/apiKeysUsage#full-sample-calculation
        dict with several keys:
        - time until request expires (I give it 5s)
        - api-key
        - api-signature  (included in header as opposed to binance)

        # For example:
        #
        verb = 'GET'
        # url-encoding on querystring - this is '/api/v1/instrument?filter={"symbol": "XBTM15"}'
        # Be sure to HMAC *exactly* what is sent on the wire
        path = '/api/v1/instrument?filter=%7B%22symbol%22%3A+%22XBTM15%22%7D'
        expires = 1518064237 # 2018-02-08T04:30:37Z
        data = ''

        Biggest Confusion was: "data" part mentionin doc (aka. body) of requests is never used here.
        Instead all our 'data' is part of the URL, added after '?'.
        '''
        headers = {}
        expires = str(int(round((time.time() + 5)))) #from float(with millisecond decimals) to int (seconds) to str
        headers['api-expires'] = expires # not calling function to ensure its same as in url
        headers['api-key'] = self._public_key

        # SIGNATURE
        # doc says 'calculated as hex(HMAC_SHA256(apiSecret, verb + path + expires + data))'

        path = urllib.parse.urlparse(self._base_url).path # removes base, to get e.g. "/api/v1"
        if len(data) > 0:
            message = bytes(method + path + endpoint + '?' + urlencode(data) + expires, 'utf-8')
        else:
            message = bytes(method + path + endpoint + expires, 'utf-8')

        signature = hmac.new(self._secret_key.encode(), message, digestmod=hashlib.sha256).hexdigest()
    
        headers['api-signature'] = signature
        # print('header:', headers)
        return headers



    def _make_requests(self, method: str, endpoint: str, data: dict):
        if method == 'GET':
            try:
                response = requests.get(self._base_url + endpoint, params=data,
                headers=self._add_headers(method, endpoint, data))
            except Exception as e:
                logger.error(f"Connection error while making {method} request to {endpoint}: {e}")
                return None  # because we won't even have a response.status_code
        elif method == 'POST':
            try:
                response = requests.post(self._base_url + endpoint, params=data,
                headers=self._add_headers(method, endpoint, data))
            except Exception as e:
                logger.error(f"Connection error while making {method} request to {endpoint}: {e}")
                return None  # because we won't even have a response.status_code
        elif method == "DELETE":
            try:
                response = requests.delete(self._base_url + endpoint, params=data,
                headers=self._add_headers(method, endpoint, data))
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
        # https://www.bitmex.com/api/explorer/#/Instrument has to realize they call contracts "instruments"
        exchange_info = self._make_requests('GET', '/instrument/active', dict())
        contracts = {}

        if exchange_info is not None:
            for contract in exchange_info:
                contracts[contract['symbol']] = Contract(contract, 'bitmex')

        return contracts


    def get_balances(self) -> dict[str, Balance]:
        data = dict()
        data['currency'] = 'all'

        margin_data = self._make_requests('GET', '/user/margin', data)

        balances = {}
        if margin_data is not None:
            for a in margin_data:
                balances[a['currency']] = Balance(a, 'bitmex')

        return balances

    
    def get_historical_candles(self, contract: Contract, timeframe: str) -> list[Candle]:
        data = {}

        data['symbol'] = contract.symbol
        data['partial'] = True #whether unfinished candles are returned (e.g. last 30min of 1h interval)
        data['binSize'] = timeframe
        data['count'] = 500 #max. per api call

        raw_candles = self._make_requests('GET', '/trade/bucketed', data)

        candles = []
        if raw_candles is not None:
            for c in raw_candles:
                candles.append(Cancle(c, 'bitmex'))


    def place_order(self, contract: Contract, order_type: str, quantity: int, side:str, price=None, tif=None) -> OrderStatus:
        data = dict()
        data['symbol'] = contract.symbol
        data['side'] = side.capitalize() #reduce user error, size->Size
        data['orderQty'] = quantity
        data['ordType'] = order_type.capitalize()


        if price is not None:
            data['price'] = price

        if tif is not None:
            data['timeInForce'] = tif

        order_status = self._make_requests('POST', '/order', data)

        if order_status is not None:
            order_status = OrderStatus(order_status, 'bitmex')

        return order_status


    def cancel_order(self, order_id: str):
        data = {}
        data['orderID'] = order_id

        order_status = self._make_requests('DELETE', '/order', data)
        #returns a list (multiple orders could be cancelled at once) we wont use that, so first entry only [0]
        if order_status is not None:
            order_status = OrderStatus(order_status[0], 'bitmex') 

        return order_status

    def get_order_status(self, order_id: str, contract: Contract):
        # Cant pass order_id, have to first get list of all orders for given symbol.
        data = {}
        data['symbol'] = contract.symbol

        order_status = self._make_requests('GET', '/order', data)

        if order_status is not None:
            for order in order_status:
                if order['orderID'] == order_id:
                    return OrderStatus(order_status, 'bitmex') 


    def _start_ws(self):
        self._ws = websocket.WebSocketApp(self._wss_url, on_open=self._on_open, on_close=self._on_close,
        on_error=self._on_error, on_message=self._on_message)

        while True:  # By putting run_forever() in infinite while loop, it will restart if connection is interrupted.
                     # Because any websocket error will trigger except statement, after which code continues
            try:
                self._ws.run_forever()  # check above under __init__ how to deal with this infinite loop problem in python
            except Exception as e:
                logger.error("Bitmex error in run_forever() method: {e}")
            time.sleep(2)


    def _on_open(self):  #some versions may need "ws" as input argument here
        logger.info("Bitmex connection opened")

        self.subscribe_channel(list(self.contracts.values()), 'bookTicker')  #not sure why its contracts.values here and not keys...


    def _on_close(self):
        logger.warning("Binance websocket connection closed")

    def _on_error(self, msg: str):
        logger.error(f"Binance connection error: {msg}")


    def subscribe_channel(self, contracts: list[Contract], channel: str):
        # https://testnet.bitmex.com/app/wsAPI
        data = dict()
        data['op'] = 'subscribe'
        data['args'] =[]

        for contract in contracts:
            data['args'].append(channel + ':' + contract.symbol.upper())  # e.g. orderBookL2_25:XBTUSD
        data['id'] = self._ws_id

        # print(data, type(data))
        # print(json.dumps(data), type(json.dumps(data))) # looks the same, but dumps() turns it into json string
        try:
            self._ws.send(json.dumps(data)) #send method expects string, not dict
        except Exception as e:
            logger.error(f"Websocket error while subscribing to {len(contracts)} {channel} updates: {e}")

        self._ws_id += 1  # instance variable from init, increase for every subscription