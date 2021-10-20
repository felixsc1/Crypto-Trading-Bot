#%%
import logging
import requests
import time

import hmac
import hashlib
import urllib.parse
from urllib.parse import urlencode

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
        else:
            self._base_url = 'https://www.bitmex.com/api/v1'

        self._public_key = public_key
        self._secret_key = secret_key

        #unlike binance, more info like time and the signature are all included in the header:
     
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
        # verb=POST
        # url=/api/v1/order
        # expires=1518064237
        # data={"symbol":"XBTUSD","quantity":1,"price":52000.50}
        # message='POST/api/v1/order1518064237{"symbol":"XBTUSD","quantity":1,"price":52000.50}'
        # signature = HEX(HMAC_SHA256(secret, message))

        Biggest Confusion was: "data" part (aka. body) of requests is never used here. Instead all our 'data' is
        part of the URL, added after '?'.
        '''
        headers = {}
        expires = str(int(round((time.time() + 5)))) #from time object to int to str
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
        print('header:', headers)
        return headers



    def _make_requests(self, method: str, endpoint: str, data: dict):
        if method == 'GET':
            response = requests.get(self._base_url + endpoint, params=data,
             headers=self._add_headers(method, endpoint, data))
        elif method == 'POST':
            response = requests.post(self._base_url + endpoint, params=data,
             headers=self._add_headers(method, endpoint, data))
        
        return response.json()


    def get_contracts(self):
        # https://www.bitmex.com/api/explorer/#/Instrument has to realize they call contracts "instruments"
        exchange_info = self._make_requests('GET', '/instrument/active', dict())
        # print(exchange_info)
        contracts = []
        for contract in exchange_info:
            contracts.append(contract['symbol'])
        return contracts


    def place_order(self, symbol, side, orderQty, price):
        data = dict()
        data['symbol'] = symbol
        data['side'] = side #default is buy
        data['ordType'] = 'Limit'
        data['orderQty'] = orderQty
        data['price'] = price

        order_status = self._make_requests('POST', '/order', data)
        return order_status