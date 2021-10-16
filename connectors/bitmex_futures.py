#%%
import logging
import requests
import pprint

#%%
# logger = logging.getLogger()

def get_contracts():
    response_object = requests.get('https://testnet.bitmex.com/api/v1/instrument/active')
    print(response_object.status_code)
    # pprint.pprint(response_object.json())

    contracts = []

    for contract in response_object.json():
        contracts.append(contract['symbol'])

    return contracts

# print(get_contracts())