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
        data['reverse'] = True #to show newest 500 candles not oldest 500

        raw_candles = self._make_requests('GET', '/trade/bucketed', data)

        candles = []
        if raw_candles is not None:
            for c in reversed(raw_candles):  #again, time order in Bitmex is weird, oldest appear first
                candles.append(Candle(c, timeframe, 'bitmex'))


    def place_order(self, contract: Contract, order_type: str, quantity: int, side:str, price=None, tif=None) -> OrderStatus:
        data = dict()
        data['symbol'] = contract.symbol
        data['side'] = side.capitalize() #reduce user error, size->Size
        data['orderQty'] = round(round(quantity / contract.lot_size) * contract.lot_size, 8) #last round() is to prevent python floating point problem that adds somethign beyond 8decimals
        data['ordType'] = order_type.capitalize()


        if price is not None:
            data['price'] = round(round(price / contract.tick_size) * contract.tick_size, 8)

        if tif is not None:
            data['timeInForce'] = tif

        order_status = self._make_requests('POST', '/order', data)
        # print(order_status) 

        if order_status is not None:
            order_status = OrderStatus(order_status, 'bitmex')

        return order_status


    def cancel_order(self, order_id: str) -> OrderStatus:
        data = {}
        data['orderID'] = order_id

        order_status = self._make_requests('DELETE', '/order', data)
        #returns a list (multiple orders could be cancelled at once) we wont use that, so first entry only [0]
        if order_status is not None:
            order_status = OrderStatus(order_status[0], 'bitmex') 

        return order_status

    def get_order_status(self, order_id: str, contract: Contract) -> OrderStatus:
        # Cant pass order_id, have to first get list of all orders for given symbol.
        data = {}
        data['symbol'] = contract.symbol

        order_status = self._make_requests('GET', '/order', data)

        if order_status is not None:
            for order in order_status:
                if order['orderID'] == order_id:
                    return OrderStatus(order_status[0], 'bitmex') 


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

        self.subscribe_channel('instrument')


    def _on_close(self):
        logger.warning("Bitmex websocket connection closed")


    def _on_error(self, msg: str):
        logger.error(f"Bitmex connection error: {msg}")


    def _on_message(self, msg: str):

        data = json.loads(msg)

        if "table" in data:
            if data['table'] == 'instrument':
            
                for d in data['data']:
                    symbol = d['symbol']

                    if symbol not in self.prices:
                        self.prices[symbol] = {'bid': None, 'ask': None} #just initialize symbol without values

                    if 'bidPrice' in d:
                        self.prices[symbol]['bid'] = d['bidPrice']
                    if 'askPrice' in d:
                        self.prices[symbol]['ask'] = d['askPrice']

                    print(symbol, self.prices[symbol])



    def subscribe_channel(self, topic: str):
        # https://testnet.bitmex.com/app/wsAPI
        # Difference to binance: dont need to loop through contracts, can subscribe to feed of all instruments at once.
        data = dict()
        data['op'] = 'subscribe'
        data['args'] =[]
        # data['args'].append(channel + ':' + contract.symbol.upper())  # i think in principle it could be filtered like this e.g. orderBookL2_25:XBTUSD
        data['args'].append(topic)

        try:
            self._ws.send(json.dumps(data)) #send method expects string, not dict
        except Exception as e:
            logger.error(f"Websocket error while subscribing to {len(contracts)} {channel} updates: {e}")

