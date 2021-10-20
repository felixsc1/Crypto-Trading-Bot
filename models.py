BITMEX_MULTIPLIER = 0.00000001 # satoshi to BTC

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
    def __init__(self, candle_info, exchange):
        if exchange =='binance':
            self.timestamp = candle_info[0]
            self.open = float(candle_info[1])
            self.high = float(candle_info[2])
            self.low = float(candle_info[3])
            self.close = float(candle_info[4])
            self.volume = float(candle_info[5])
        elif exchange =='bitmex':
            # returns list of dicts (in which numbers are already floats) instead of a list in binance.
            self.timestamp = candle_info['timestamp']
            self.open = candle_info['open']
            self.high = candle_info['high']
            self.low = candle_info['low']
            self.close = candle_info['close']
            self.volume = candle_info['volume']


class Contract:
    def __init__(self, contract_info, exchange):
        if exchange =='binance':
            self.symbol = contract_info['symbol']
            self.base_asset = contract_info['baseAsset']
            self.quote_asset = contract_info['quoteAsset']
            self.price_decimals = contract_info['pricePrecision']
            self.quantity_decimals = contract_info['quantityPrecision']
        elif exchange == 'bitmex':
            self.symbol = contract_info['symbol']
            self.base_asset = contract_info['rootSymbol']
            self.quote_asset = contract_info['quoteCurrency']
            self.price_decimals = contract_info['tickSize']
            self.quantity_decimals = contract_info['lotSize']

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