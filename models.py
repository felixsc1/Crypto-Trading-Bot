import dateutil.parser
import datetime

BITMEX_MULTIPLIER = 0.00000001 # satoshi to BTC
BITMEX_TF_MINUTES = {'1m': 1, '5m': 5, '1h': 60, '1h': 1440}

class Balance:
    '''
    rather than working with the dictionaries provided by the API, we create own model for the data.
    Don't have to look up the documentation/code to find things everytime.
    Instead: typing balances. --> auto complete will suggest the available instance variables defined below
    '''
    def __init__(self, info, exchange):
        if exchange =='binance':
            self.initial_margin = float(info['initialMargin'])
            self.maintenance_margin = float(info['maintMargin'])
            self.margin_balance = float(info['marginBalance'])
            self.wallet_balance = float(info['walletBalance'])
            self.unrealized_pnl = float(info['unrealizedProfit'])
        elif exchange =='bitmex':
            # user wallet on bitmex is always in bitcoin, values here are returned in satoshis
            self.initial_margin = info['initMargin'] * BITMEX_MULTIPLIER
            self.maintenance_margin = info['maintMargin'] * BITMEX_MULTIPLIER
            self.margin_balance = info['marginBalance'] *BITMEX_MULTIPLIER
            self.wallet_balance = info['walletBalance'] * BITMEX_MULTIPLIER
            self.unrealized_pnl = info['unrealisedPnl'] * BITMEX_MULTIPLIER


class Candle:
    # Note, how this will make it much easier to reference the different information, instead of using meaningless numbers of an array.
    def __init__(self, candle_info, timeframe, exchange):
        if exchange =='binance':
            self.timestamp = candle_info[0]
            self.open = float(candle_info[1])
            self.high = float(candle_info[2])
            self.low = float(candle_info[3])
            self.close = float(candle_info[4])
            self.volume = float(candle_info[5])
        elif exchange =='bitmex':
            # returns list of dicts (in which numbers are already floats) instead of a list in binance.
            self.timestamp = dateutil.parser.isoparse(candle_info['timestamp']) #get from iso8601 string to millisecond unix timestamp
            self.timestamp = self.timestamp - datetime.timedelta(minutes=BITMEX_TF_MINUTES[timeframe])
            print(self.timestamp)
            self.timestamp = int(self.timestamp.timestamp() * 1000) 
            self.open = candle_info['open']
            self.high = candle_info['high']
            self.low = candle_info['low']
            self.close = candle_info['close']
            self.volume = candle_info['volume']


def tick_to_decimals(tick_size: float) -> int:
    #for explanation see Lesson 23
    tick_size_str = "0:.8f".format(tick_size) # otherwise displaying small number a s string will show scientific notation
    while tick_size_str[-1] == "0":
        tick_size_str = tick_size_str[:-1] #remove trailing zeros

    split_tick = tick_size_str.split(".")
    if len(split_tick) > 1:  #meaning if there is a dot in the string
        return len(split_tick[1]) #e.g. for 0.001 --> returns 3
    else:
        return 0 #no decimals


class Contract:
    def __init__(self, contract_info, exchange):
        if exchange =='binance':
            self.symbol = contract_info['symbol']
            self.base_asset = contract_info['baseAsset']
            self.quote_asset = contract_info['quoteAsset']
            self.price_decimals = contract_info['pricePrecision']
            self.quantity_decimals = contract_info['quantityPrecision']
            self.tick_size = 1/pow(10, contract_info['pricePrecision']) #e.g. when precision is 3 decimals, divide by 1000
            self.lot_size = 1/pow(10, contract_info['quantityPrecision'])
        elif exchange == 'bitmex':
            self.symbol = contract_info['symbol']
            self.base_asset = contract_info['rootSymbol']
            self.quote_asset = contract_info['quoteCurrency']
            self.price_decimals = tick_to_decimals(contract_info['tickSize'])
            self.quantity_decimals = tick_to_decimals(contract_info['lotSize'])
            self.tick_size = contract_info['tickSize']
            self.lot_size = contract_info['lotSize']

class OrderStatus:
    def __init__(self, order_info, exchange):
        if exchange =='binance':
            self.order_id = order_info['orderId']
            self.status = order_info['status']
            self.avg_price = float(order_info['avgPrice'])
        if exchange =='bitmex':
            self.order_id = order_info['orderID']
            self.status = order_info['ordStatus']
            self.avg_price = order_info['avgPx']