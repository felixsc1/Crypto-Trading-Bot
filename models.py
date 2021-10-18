class Balance:
    '''
    rather than working with the dictionaries provided by the API, we create own model for the data.
    Don't have to look up the documentation/code to find things everytime.
    Instead: typing balances. --> auto complete will suggest the available instance variables defined below
    '''
    def __init__(self, info):
        self.initial_margin = float(info['initialMargin'])
        self.maintenance_margin = float(info['maintMargin'])
        self.margin_balance = float(info['marginBalance'])
        self.wallet_balance = float(info['walletBalance'])
        self.unrealized_pnl = float(info['crossUnPnl'])


class Candle:
    # Note, how this will make it much easier to reference the different information, instead of using numbers of an array.
    def __init__(self, candle_info):
        self.timestamp = candle_info[0]
        self.open = float(candle_info[1])
        self.high = float(candle_info[2])
        self.low = float(candle_info[3])
        self.close = float(candle_info[4])
        self.volume = float(candle_info[5])


class Contract:
    def __init__(self, contract_info):
        self.symbol = contract_info['symbol']
        self.base_asset = contract_info['baseAsset']
        self.quote_asset = contract_info['quoteAsset']
        self.pice_decimals = contract_info['pricePrecision']
        self.quantity_decimals = contract_info['quantityPrecision']


class OrderStatus:
    def __init__(self, order_info):
        self.order_id = order_info['orderId']
        self.status = order_info['status']
        self.avg_price = float(order_info['avgPrice'])