# %%
import tkinter as tk
import logging
# from connectors.bitmex_futures import get_contracts
from connectors.binance_futures import BinanceFuturesClient
from connectors.bitmex_futures import BitmexFuturesClient

# %%
# logger setup
#see corey schaefer tutorial on logging!
logger = logging.getLogger()

logger.setLevel(logging.DEBUG) #only info and above is displayed

stream_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s :: %(message)s' )
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler('info.log')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

# test examples
# logger.debug('message when debugging the program')
# logger.info('shows some basic information')
# logger.warning('about something you should pay attention to')
# logger.error('message to debug an error in the program')


if __name__ == '__main__':

    with open('apikeys.txt') as apikeys:
        lines = apikeys.read().splitlines() 
    binance_public_key = lines[10]
    binance_secret_key = lines[12]
    bitmex_public_key = lines[4]
    bitmex_secret_key = lines[6]

    # binance = BinanceFuturesClient(binance_public_key, binance_secret_key, True)

    # some testing calls NEWEST to oldest:
    # Note: all test code below breaks after Lesson 15, when data format is changed with "models.py"
    # print(binance.cancel_order('BTCUSDT', 2827960728))
    # print(binance.get_order_status('BTCUSDT', 2827960728)) #ID was given by place_order call below
    # print(binance.place_order('BTCUSDT', 'BUY', 0.01, 'LIMIT', 20000, 'GTC'))
    # print(binance.get_balances())
    # print(binance.get_contracts())
    # print(binance.get_bid_ask(('BTCUSDT')))
    # print(binance.get_historical_candles('BTCUSDT', '1h'))

    bitmex = BitmexFuturesClient(bitmex_public_key, bitmex_secret_key, True)
    # print(bitmex.place_order('ETHUSD', 'Buy', 10, 100))
    # print(bitmex.get_contracts())



    root = tk.Tk()  # main window of app

# below was just example from section 2, removed in section 3:

    # bitmex_contracts = get_contracts()
    # root.configure(bg="gray12")
    # i = 0
    # j = 0
    # calibri_font = ("Calibri", 11, "normal")
    # for contract in bitmex_contracts:
    #     # label_widget = tk.Label(root,text=contract, borderwidth=1, relief=tk.RIDGE, width=13)
    #     label_widget = tk.Label(root,text=contract, bg='gray12', fg='SteelBlue1', font=calibri_font, width=13)
    #     label_widget.grid(row=i, column=j, sticky='ew')  #for tabular data usually grid. pack() method for small numbers
    #     #try without sticky argument, then the entries in columns dont look uniform.
    #     #for colors see: http://www.science.smith.edu/dftwiki/images/3/3d/TkInterColorCharts.png

    #     if i == 4:  # here we put 5 names in a column, after that start new column.
    #         j += 1
    #         i = 0
    #     else:
    #         i += 1

    root.mainloop()

# %%
