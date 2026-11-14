from typing import Optional, List
import pandas as pd
import pandas_ta as ta
import ccxt
from execution_service import HyperLiquidExecutionService
from discord import SyncWebhook
import json
import threading
import time

lock = threading.Lock()

SUPPORTED_TFS = ("1m", "15m", "1h", "4h", "1d")
STRAT_TYPES = ("hma", "ma")
HISTORY_LIMIT = 250
# HMA (nested WMAs) needs about length + floor(sqrt(length)) + 2 bars of warmup
# before the last closed candles are non-NaN, so reserve headroom inside the window.
MAX_INDICATOR_LENGTH = HISTORY_LIMIT - 20

class Asset:
    def __init__(self, id : int, rawAssetName : str, tf : str, hyperliquidBot : HyperLiquidExecutionService, is_longStrat : bool, stratType : str = "hma"):
        if stratType not in STRAT_TYPES:
            raise ValueError(f"Invalid strategy type: {stratType}")

        self.id = id
        self.coinpair = rawAssetName.upper() + "USDT"
        self.rawAssetName = rawAssetName.upper()
        self.tf = tf
       
        self.is_longStrat = is_longStrat
        self.stratType = stratType
        
        self.history = None
        self.trend = None
        self.nextUpdate = None
        self.leverage = None
        self.exist = True
        self.hyperLiquidBot = hyperliquidBot 
        self.txn_USDTAmount = 20
        self.length = 96
        self.TotalAccountValue = None
        
        
        configFile = open("config.json", "r")
        configFile = configFile.read()
        
        exchange = json.loads(configFile)["exchange"]
        if exchange == "binance":
            self.exchange = ccxt.binance()
        elif exchange == "bybit":
            self.exchange = ccxt.bybit()
        else:
            print("Invalid exchange in config.json")
            return
        
        
        
        webhookUrl = json.loads(configFile)["webhook"]
        self.webhook = SyncWebhook.from_url(webhookUrl)
        
        print("Asset loaded")
        
        # res = self.hyperLiquidBot.generate_order(self.rawAssetName, self.txn_USDTAmount, "b")
        # print(res)
        # time.sleep(5)
        # res = self.hyperLiquidBot.close_position(self.rawAssetName)

    def change_txn_amount(self, amount):
        print(f"Changing Ape Amount for {self.rawAssetName} to {amount}")
        self.txn_USDTAmount = amount
        return self.txn_USDTAmount
        
        
    def get_historical_data(self):
        time.sleep(5) 
        
        retry = 0
        data = None
        while retry < 3:
            try:
                data = self.exchange.fetch_ohlcv(self.coinpair, self.tf, limit=HISTORY_LIMIT)
                break
            except Exception as e:
                print(e)
                retry += 1
                time.sleep(5)

        if retry == 3:
            self.webhook.send(f"@everyone Error fetching data for {self.coinpair}")
            self.exist = False
            return
        
        
        
        data = [[self.exchange.iso8601(candle[0])] + candle[1:] for candle in data]
        header = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
        df = pd.DataFrame(data, columns=header)
        self.history = df
        
        lastTimestamp = df["Timestamp"].iloc[-1]
        
        nextTimestamp = None
        if self.tf == "1m":
            nextTimestamp = pd.Timestamp(lastTimestamp) + pd.Timedelta(minutes=1)
            
        if self.tf == "15m":
            nextTimestamp = pd.Timestamp(lastTimestamp) + pd.Timedelta(minutes=15)
        
        if self.tf == "1h":
            nextTimestamp = pd.Timestamp(lastTimestamp) + pd.Timedelta(hours=1)

        if self.tf == "4h":
            nextTimestamp = pd.Timestamp(lastTimestamp) + pd.Timedelta(hours=4)

        if self.tf == "1d":
            nextTimestamp = pd.Timestamp(lastTimestamp) + pd.Timedelta(days=1)

        
        self.nextUpdate = nextTimestamp.replace(tzinfo=None)            


    def generateSignal(self):
        if self.stratType == "ma":
            self.generateSignalMA()
        else:
            self.generateSignalHMA()
    
    
    def generateSignalHMA(self):
        df = self.history
        df["HMA"] = df.ta.hma(series=df["Close"], length=self.length)
        last = df["HMA"].iloc[-2] 
        secondLast = df["HMA"].iloc[-3]
        
        print(f"{self.coinpair} HMA Last: {last} Second Last: {secondLast}")
        
        if pd.isna(last) or pd.isna(secondLast):
            print(f"{self.coinpair} Not enough candles to compute HMA{self.length}")
            return
                        
        if self.trend == None:
            print(f"{self.coinpair} Initialising HMA Trend as {last > secondLast}")
            self.trend = bool(last > secondLast)
            return
        
        buycondition = last > secondLast and self.trend == False
        sellcondition = last < secondLast and self.trend == True
        
        if buycondition:
            self.buySignal()
        
        if sellcondition:
            self.sellSignal()
    
    
    def generateSignalMA(self):
        df = self.history
        df["MA"] = df.ta.sma(series=df["Close"], length=self.length)
        close = df["Close"].iloc[-2]
        ma = df["MA"].iloc[-2]
        
        print(f"{self.coinpair} Close: {close} MA{self.length}: {ma}")
        
        if pd.isna(ma):
            print(f"{self.coinpair} Not enough candles to compute MA{self.length}")
            return
        
        trend = bool(close > ma)
        
        if self.trend == None:
            print(f"{self.coinpair} Initialising MA Trend as {trend}")
            self.trend = trend
            return
        
        # price crossing the MA flips the trend
        if trend and self.trend == False:
            self.buySignal()
        
        if not trend and self.trend == True:
            self.sellSignal()
    
    
    def buySignal(self):
        print(f"{self.coinpair} Buy Signal on {self.tf} timeframe")
        self.trend = True
        
        self.webhook.send(f"@everyone {self.coinpair} Buy Signal on {self.tf} timeframe")
        
        if self.is_longStrat:
            with lock:                    
                self.hyperLiquidBot.generate_order(self.rawAssetName, self.txn_USDTAmount, True)
            
        if not self.is_longStrat:
            with lock:
                self.hyperLiquidBot.close_position(self.rawAssetName)
    
    
    def sellSignal(self):
        print(f"{self.coinpair} Sell Signal on {self.tf} timeframe")
        self.trend = False
        
        self.webhook.send(f"@everyone {self.coinpair} Sell Signal on {self.tf} timeframe")
        
        if self.is_longStrat:
            with lock:
                self.hyperLiquidBot.close_position(self.rawAssetName)
            
        if not self.is_longStrat:
            with lock:
                self.hyperLiquidBot.generate_order(self.rawAssetName, self.txn_USDTAmount, False)
    
    
    # OLD RUN        
    # def run(self):
    #     # # MUST REMOVE THIS
    #     # print(f"{self.coinpair} {self.tf} Running. Sleeping")
    #     # time.sleep(100)
    #     # print(f"{self.coinpair} {self.tf} Waking up")
        
    #     while True:
    #         if self.exist == False:
    #             return
            
    #         self.get_historical_data()
    #         self.generateSignal()
                
    #         timeToSleep = self.nextUpdate - pd.Timestamp.utcnow().replace(tzinfo=None)
    #         timeToSleepSeconds = timeToSleep.total_seconds()
    #         print(f"{self.coinpair} {self.tf} Sleeping for {timeToSleep}")
            
    #         if timeToSleepSeconds > 0:
    #             time.sleep(timeToSleepSeconds)
    #         else:
    #             self.webhook.send(f"@everyone Error: {self.coinpair} {self.tf} Time to sleep is negative. Retrying.")
    #             time.sleep(5)
    
    def run(self):
        self.get_historical_data()
        self.generateSignal()

        while True:
            if self.exist == False:
                return
            
            currenttime = pd.Timestamp.utcnow().replace(tzinfo=None)
            nextupdate = self.nextUpdate
            condition = currenttime >= nextupdate
            
            if condition:
                print(f"{self.coinpair} {self.tf} running inside condition.")
                self.get_historical_data()
                self.generateSignal()
                
            
            diff = nextupdate - currenttime
            diff_seconds = diff.total_seconds()
            
            # ensure that bot wakes up precisely at the next candle
            if diff_seconds < 30:
                if diff_seconds > 0:
                    print(f"{self.coinpair} {self.tf} Sleeping for {diff}")
                    time.sleep(diff_seconds)
                else:
                    print(f"{self.coinpair} {self.tf} Sleeping for 0.1 second")
                    time.sleep(0.1)
            else:
                print(f"{self.coinpair} {self.tf} Sleeping for 20 seconds")
                time.sleep(20)                

class Screener:
    def __init__(self):
        self.assets =  []
        self.idcount = 0
        self.hyperliquidBot : Optional[HyperLiquidExecutionService] = None 
        print("Screener loaded")
        
    def addAsset(self, asset : str, tf : str , length : int, size : float, leverage : int, is_long : bool, stratType : str = "hma"):
        if tf not in SUPPORTED_TFS:
            raise ValueError(f"Unsupported timeframe: {tf}")

        if length is not None and (length <= 0 or length > MAX_INDICATOR_LENGTH):
            raise ValueError(f"Invalid length: {length}")

        a = Asset(self.idcount, asset, tf, self.hyperliquidBot, is_long, stratType)
        
        if size != None:
            a.change_txn_amount(size)
            
        if length != None:
            a.length = length
            
        if leverage != None:
            self.hyperliquidBot.set_leverage(a.rawAssetName, leverage) 
            a.leverage = leverage   
        
        t = threading.Thread(target=a.run)
        t.daemon = True
        t.start()
        
        self.assets.append(a)
        self.idcount += 1
    
        
    def removeAsset(self, id):
        for a in self.assets:
            a : Asset
            if a.id == id:
                a.exist = False
                self.assets.remove(a)
                print(f"Removed {a.coinpair}")
                return


# h = HyperLiquidExecutionService()
# s = Screener()
# s.hyperliquidBot = h

# s.addAsset("btc", "1m", 1, 96, 10, 10)
# s.addAsset("sol", "1m", 1, 96, 20, 10)
# s.addAsset("eth", "1m", 1, 96, 20, 10)

# time.sleep(20)

# s.removeAsset(0)
   
# async def infiniteLoop():
#     while True:
#         await asyncio.sleep(100)
        

# asyncio.run(infiniteLoop())