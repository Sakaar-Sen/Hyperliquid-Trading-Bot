from hyperliquid.utils import constants
import example_utils
import ccxt
import json
from typing import Optional
import requests
from math import log10, floor
from discord import SyncWebhook


specialAssets = ["PEPE", "SHIB", "FLOKI", "BONK"]

class HyperLiquidExecutionService:
    def __init__(self, password):
        self.address, self.info, self.exchange = example_utils.setup(constants.MAINNET_API_URL, skip_ws=True, password=password)
        
        configFile = open("config.json", "r")
        configFile = configFile.read()
            
        exchange = json.loads(configFile)["exchange"]
        
        if exchange == "binance":
            self.ex = ccxt.binance()
            
        elif exchange == "bybit":
            self.ex = ccxt.bybit()
            
        else:
            print("Invalid exchange in config.json")
            return
        
        webhookUrl = json.loads(configFile)["webhook"]
        self.infoBook = self.get_infoForAll()
        self.webhook = SyncWebhook.from_url(webhookUrl)

        print("hyperliquid loaded")
            
            
    def get_last_price(self, rawAssetName : str):
        retry = 5
        while retry > 0:
            try:
                symbol = rawAssetName.upper() + "USDT"
                r = self.ex.fetch_ticker(symbol)
                return r["last"]
            except Exception as e:
                print("Cannot get last price for " + symbol)
                self.webhook.send(f"@everyone Cannot get last price for {symbol}. Retrying in 10 secs.")
                retry -= 1


    def get_asset_name(self, rawAssetName : str):
        rawAssetName = rawAssetName.upper()
        if rawAssetName in specialAssets:
            rawAssetName = "k" + rawAssetName
        return rawAssetName

    
    def get_amtofopenpositions(self, rawAssetName : str):
        AssetName = self.get_asset_name(rawAssetName)
            
        openPositions = self.get_allOpenPositionsTicker()
        count = 0
        
        for i in openPositions:
            if i == AssetName:
                count += 1
                
        return count
    
    def get_leverage(self, rawAssetName : str) -> int:
        AssetName = self.get_asset_name(rawAssetName)
        
        user_state = self.info.user_state(self.address)
        
        lev = None
        print(user_state)
        for asset_position in user_state["assetPositions"]:
            if asset_position["position"]["coin"] == AssetName:
                lev = asset_position["position"]["leverage"]


        return lev['value']
    
    
    def set_leverage(self, rawAssetName : str, leverage : int):
        AssetName = self.get_asset_name(rawAssetName)
            
        res = self.exchange.update_leverage(leverage, AssetName, False)
        #{'status': 'err', 'response': 'Cannot decrease leverage with open position.'}
        #{'status': 'ok', 'response': {'type': 'default'}}
        if res["status"] == "err":
            self.webhook.send(f'@everyone Error while setting leverage for {rawAssetName} \nError: {res["response"]}')
        if res["status"] == "ok":
            self.webhook.send(f'@everyone Leverage set for {rawAssetName} to {leverage}')
        
        return res
    
    
    def get_margin_summary(self):
        user_state = self.info.user_state(self.address)
        return user_state["marginSummary"]
    
    
    def get_all_open_orders(self):
        user_state = self.info.open_orders(self.address)
        return user_state
        
        
    def get_all_open_positions(self):
        user_state = self.info.user_state(self.address)
       # print(user_state)
        return user_state["assetPositions"]
        
        
    def get_allOpenPositionsTicker(self) -> list:
        res = self.get_all_open_positions()
        tickers = []
        for i in res:
            #print(i['position']['coin'])
            tickers.append(i['position']['coin'])

        return tickers


    def get_infoForAll(self):
        url = "https://api.hyperliquid.xyz/info"
        headers = {
            "Content-Type": "application/json"
        }
        body = {
            "type": "meta"
        }

        res = requests.post(url, headers=headers, data=json.dumps(body))
        res = json.loads(res.text)
        
        return res['universe']
    
    
    def get_info_forAsset(self, rawAssetName : str):
        AssetName = self.get_asset_name(rawAssetName)
        
        info = self.infoBook
        
        for asset in info:
            if asset['name'] == AssetName:
                return asset
        return None
    
    def get_correct_price(self, AssetName : str, price : float) -> float:
        if AssetName.startswith("k"):
            price = price * 1000
        return float(price)
              
              
    def round_to_5_sig_digs(self, x : float):
        return round(x, -int(floor(log10(abs(x))) - 4))


    @staticmethod
    def _error_message(result) -> str:
        # SDK errors come back as {"status": "err", "response": "text"}; successful
        # responses use a dict. Normalise both before putting them in a message.
        response = result.get("response")
        if isinstance(response, dict):
            return str(response.get("error", response))
        return str(response)


    def set_tp(self, AssetName : str, tpPrice : float, assetAmount : float, is_buy : bool):
            
        tpPrice = self.round_to_5_sig_digs(tpPrice)
        tpPrice = round(tpPrice, 6)
        
        take_profit_order_type = {"trigger": {"triggerPx": tpPrice, "isMarket": True, "tpsl": "tp"}}
        
        result = self.exchange.order(AssetName, is_buy, assetAmount, tpPrice, take_profit_order_type, reduce_only=True)
        
        print(result)
        if result["status"] == "ok":
            try:
                resting = result["response"]["data"]["statuses"][0]["resting"]["oid"]
                self.webhook.send(f'@everyone TP Set for {AssetName} at {tpPrice}')
                self.webhook.send(f'{resting}')
            except KeyError:
                self.webhook.send(f'@everyone Error while setting TP for {AssetName} \nError: {result["response"]["data"]["statuses"][0]["error"]}')
        else:
            self.webhook.send(f"@everyone Error setting TP for {AssetName}.")
            self.webhook.send(f'Error: {self._error_message(result)}')

    
    def set_sl(self, AssetName : str, slPrice : float, assetAmount : float, is_buy : bool):
            
        slPrice = self.round_to_5_sig_digs(slPrice) # from documentation, max 5 sig figs
        slPrice = round(slPrice, 6) # from documentation, max 6 decimal places
        
        stop_order_type = {"trigger": {"triggerPx": slPrice, "isMarket": True, "tpsl": "sl"}}

        result = self.exchange.order(AssetName, is_buy, assetAmount, slPrice, stop_order_type, reduce_only=True)
        
        print(result)
        if result["status"] == "ok":
            try:
                resting = result["response"]["data"]["statuses"][0]["resting"]["oid"]
                self.webhook.send(f'@everyone SL Set for {AssetName} at {slPrice}')
                self.webhook.send(f'{resting}')
            except KeyError:
                self.webhook.send(f'@everyone Error while setting SL for {AssetName} \nError: {result["response"]["data"]["statuses"][0]["error"]}')
        else:
            self.webhook.send(f"@everyone Error setting SL for {AssetName}.")
            self.webhook.send(f'Error: {self._error_message(result)}')
        
        
    def get_decimals_forAsset(self, rawAssetName : str):
        AssetName = self.get_asset_name(rawAssetName)
        try:
            info = self.get_info_forAsset(AssetName)
            szDecimal = info['szDecimals']
            return szDecimal
        except:
            return None
  

    
    def cancel_limit_order(self, rawAssetName : str, oid):
        AssetName = self.get_asset_name(rawAssetName)
        
        #When perpetual endpoints expect an integer for asset, use the index of the coin found in the meta info response. E.g. BTC = 0 on mainnet.
        oid = int(oid)
        
        order_result = self.exchange.cancel(AssetName, oid)
        
        if order_result["status"] == "ok":
            status = order_result["response"]["data"]["statuses"][0]
            if status == "success":
                self.webhook.send(f'@everyone Limit Order for {rawAssetName} with oid {oid} has been cancelled successfully.')
                return 
            
            try:
                error = status["error"]
            except (KeyError, TypeError):
                error = status
            self.webhook.send(f'@everyone Error while cancelling Limit Order for {rawAssetName} with oid {oid}. Error: {error}')
            
    
    
    def cancel_all_orders(self, rawAssetName):
        AssetName = self.get_asset_name(rawAssetName)
        
        openOrders = self.get_all_open_orders()
        
        for i in openOrders:
            if i["coin"] == AssetName: 
                oid = i["oid"]
                self.cancel_limit_order(rawAssetName, oid)
                
        
    
    
    
    def place_limit_order(self, rawAssetName : str, is_buy : bool, assetamount : float, price : float, reduce_only : bool = False) -> Optional[float]:
        AssetName = self.get_asset_name(rawAssetName)
            
        order_type = {"limit" : {"tif": "Gtc"}}
        order_result = self.exchange.order(AssetName, is_buy, assetamount, price, order_type, reduce_only)
        
        if order_result["status"] == "ok":
            for status in order_result["response"]["data"]["statuses"]:
                    # key resting or filled must exist, only 1 of them will exist
                filled = status.get("filled")
                resting = status.get("resting")
                
                if filled == None and resting == None:
                    self.webhook.send(f'@everyone Error while filling {rawAssetName}')
                    self.webhook.send(f'Error: {status["error"]}')
                    print(f'Error: {status["error"]}')
                    return None
                
                emoji = ":green_circle:" if is_buy else ":red_circle:" 
                side = "Buy" if is_buy else "Sell"
                
                if filled != None:
                    self.webhook.send(f'@everyone Limit Order filled to {side} {rawAssetName}; filled {filled["totalSz"]} @{filled["avgPx"]} {emoji}')
                    return float(filled["totalSz"])
                
                if resting != None:
                    self.webhook.send(f'{resting["oid"]} {emoji}')
                    return float(resting["oid"])
                
                return 1
        else:
            self.webhook.send(f"@everyone Error opening limit position for {rawAssetName}.")
            self.webhook.send(f'Error: {self._error_message(order_result)}')
            return None
    
    def place_market_order(self, rawAssetName : str , is_buy : bool, assetamount : float) -> Optional[float]:  
        AssetName = self.get_asset_name(rawAssetName)      
        order_result = self.exchange.market_open(AssetName, is_buy, assetamount)
            
        if order_result["status"] == "ok":
            for status in order_result["response"]["data"]["statuses"]:
                try:
                    filled = status["filled"]
                    emoji = ":green_circle:" if is_buy else ":red_circle:" 
                    side = "Bought" if is_buy else "Sold"
                    self.webhook.send(f'@everyone Market {side} {rawAssetName}; filled {filled["totalSz"]} @{filled["avgPx"]} {emoji}')
                    positionsize = float(filled["totalSz"]) * float(filled["avgPx"])
                    self.webhook.send(f'@everyone Position Size is: {positionsize} USDT.')
                    return float(filled["totalSz"])
                except KeyError:
                    self.webhook.send(f'Error while filling {rawAssetName}')
                    self.webhook.send(f'Error: {status["error"]}')
                    print(f'Error: {status["error"]}')
                    return None
        else:
            self.webhook.send(f"@everyone Error opening position for {rawAssetName}. Retrying in 5.")
            self.webhook.send(f'Error: {self._error_message(order_result)}')
            return None
            
        
    def generate_order(self, rawAssetName : str, USDTAmount : int, is_long : bool):
        
        AssetName = self.get_asset_name(rawAssetName)
        current_price = self.get_last_price(rawAssetName)
        current_price = self.get_correct_price(AssetName, current_price)
        
        info = self.get_info_forAsset(rawAssetName)
        szDecimal = info['szDecimals']
        
        assetAmount = USDTAmount / current_price
        assetAmount = round(assetAmount, szDecimal)
        
        if szDecimal == 0:
            assetAmount = int(assetAmount)
            
        if assetAmount == 0:
            print("Asset Amount is 0")
            self.webhook.send(f"@everyone Asset Amount is 0 for {AssetName}. Unable to place order")
            return
        
        print("Asset Amount: " + str(assetAmount))
        

        res = self.place_market_order(rawAssetName, is_long, assetAmount)
    
    
        
    def close_position(self, rawAssetName : str):
        AssetName = self.get_asset_name(rawAssetName)            
            
        if AssetName not in self.get_allOpenPositionsTicker():
            self.webhook.send(f"@everyone Error closing position for {rawAssetName}. Position does not exist.")
            return
            
        order_result = self.exchange.market_close(AssetName)
            
        if order_result["status"] == "ok":
            for status in order_result["response"]["data"]["statuses"]:
                try:
                    filled = status["filled"]
                    self.webhook.send(f'@everyone Closed position for {rawAssetName}; filled {filled["totalSz"]} @{filled["avgPx"]}')
                except (KeyError, TypeError):
                    self.webhook.send(f'(close position) Error while filling {rawAssetName}')
                    print(f'Error: {status}')
            
            
    def close_all_positions(self):
        openPositions = self.get_allOpenPositionsTicker()
        print(openPositions)
        for i in openPositions:
            order_result = self.exchange.market_close(i)
            
            if order_result["status"] == "ok":
                for status in order_result["response"]["data"]["statuses"]:
                    try:
                        filled = status["filled"]
                        self.webhook.send(f'@everyone Closed position for {i}; filled {filled["totalSz"]} @{filled["avgPx"]}')
                    except (KeyError, TypeError):
                        self.webhook.send(f'(close position) Error while filling {i}')
                        print(f'Error: {status}')
    
    
    def get_totalAccValue(self) -> float:
        user_state = self.info.user_state(self.address)
        print(user_state)
        return user_state["marginSummary"]["accountValue"] 


# e = HyperLiquidExecutionService()
# e.set_leverage("PEPE", 3)
# e.generate_order("PEPE", 20, True, True, 0.00001)

# e.get_info_forAsset("BTC")

# e.set_sl("BTC", 67301.1, 0.00247)

# e.get_leverage("BTC")

# e.set_sl("kBONK", 0.03150770000000001, 10000)
# e.set_sl("kBONK", 0.031, 10000)


# e.generate_order("BTC", 10, True, True, 68100)