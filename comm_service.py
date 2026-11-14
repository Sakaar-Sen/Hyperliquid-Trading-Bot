import discord
from screener_service import Screener
from screener_service import Asset
from screener_service import SUPPORTED_TFS
from screener_service import STRAT_TYPES
from screener_service import MAX_INDICATOR_LENGTH
import asyncio
from execution_service import HyperLiquidExecutionService
from typing import Optional
import json
import math

class CommunicationService(discord.Client):
    def __init__(self, hlbot : Optional[HyperLiquidExecutionService], screener : Screener, *args, **kwargs):
        i = discord.Intents.all()
        super().__init__(intents=i)
        self.screener : Screener = screener
        self.hlbot : Optional[HyperLiquidExecutionService] = hlbot
        
        print("Comms loaded.")
        
        
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        await self.send_message("Bot is online. Use $start <password> to start the bot.")
        
        
    def get_assetListMsg(self):
        if len(self.screener.assets) == 0:
            return "No assets in the list"
        
        msg = ""
        
        for a in self.screener.assets:
            a : Asset
            trend = "Up" if a.trend else "down"
            trend = "Initializing" if a.trend == None else trend
            side = "Long" if a.is_longStrat else "Short"
            
            msg += f"ID: {a.id} \nAsset: {a.coinpair} ({int(a.leverage)}x {side}) {a.tf} \nTrend: {a.stratType.upper()} {a.length} {trend} \nSize: {a.txn_USDTAmount} \n" + '-' * 40 + "\n"
        
        hlbot = self.hlbot
        
        totalAccValue = round(float(hlbot.get_totalAccValue()), 2)
        
        msg += f"\nTotal Account Value: {totalAccValue}"
        backticks = "```"
        msg = backticks + msg + backticks
        return msg
    
    
    def create_hlbot(self, password):
        try:
            hlbot = HyperLiquidExecutionService(password)
            self.hlbot = hlbot
            self.screener.hyperliquidBot = hlbot
            return hlbot.address
        except:
            return False
    
    async def on_message(self, message : discord.Message):
        if message.author == self.user:
            return
        
        if message.content.startswith("$start"):
            # $start <password>
            args = message.content.split(" ")
            if len(args) != 2:
                await message.channel.send("Invalid arguments\nUsage: $start <password>")
                return
            
            password = args[1]
            res = self.create_hlbot(password)
            if res:
                await message.channel.send(f"running with account {res}")
            else:
                await message.channel.send("Failure")
                
        
        if message.content.startswith("$long"):
            # $long <rawAssetName> <usdt_size> <leverage>
            args = message.content.split(" ")
            print(args)
            if len(args) < 3:
                await message.channel.send("Invalid arguments\nUsage: $long <rawAssetName> <usdt_size> <leverage>")
                return
            
            rawAssetName = args[1]
            size = float(args[2])
            
            if size < 10:
                await message.channel.send("Minimum size is 10 USDT")
                return
            
            hlbot = self.hlbot
            
            if len(args) == 4:
                leverage = int(args[3])
                hlbot.set_leverage(rawAssetName, leverage)
                
            hlbot.generate_order(rawAssetName, size, True)
            await message.channel.send(f"Longed {rawAssetName} with {size} USDT")
        
        if message.content.startswith("$short"):
            # $short <rawAssetName> <usdt_size> <leverage>
            args = message.content.split(" ")
            if len(args) < 3:
                await message.channel.send("Invalid arguments\nUsage: $short <rawAssetName> <usdt_size> <leverage>")
                return
            
            rawAssetName = args[1]
            size = float(args[2])
            
            if size < 10:
                await message.channel.send("Minimum size is 10 USDT")
                return
            
            hlbot = self.hlbot
            
            if len(args) == 4:
                leverage = int(args[3])
                hlbot.set_leverage(rawAssetName, leverage)
                
            hlbot.generate_order(rawAssetName, size, False)
            await message.channel.send(f"Shorted {rawAssetName} with {size} USDT")
            
        if message.content.startswith("$limit"):
            # $limit <rawAssetName> <is_buy : 1/0> <usdt_Amount> <price> <reduce_only:1/0=0>
            args = message.content.split(" ")
            
            if len(args) != 6:
                await message.channel.send("Invalid arguments\nUsage: $limit <rawAssetName> <is_buy : 1/0> <usdt_Amount> <price> <reduce_only:1/0>")
                return
            
            rawAssetName = args[1]
            is_buy = True if args[2] == "1" else False
            usdt_Amount = float(args[3])
            price = float(args[4])
            reduce_only = True if args[5] == "1" else False
            
            hlbot = self.hlbot
            exchange = hlbot.ex
            
            # get current price
            AssetName = hlbot.get_asset_name(rawAssetName)
            price = hlbot.get_correct_price(AssetName, price)
            
            # get asset amount
            assetAmount = usdt_Amount / price
            info = hlbot.get_info_forAsset(rawAssetName)
            szDecimal = info['szDecimals']
            assetAmount = round(assetAmount, szDecimal)
            if szDecimal == 0:
                assetAmount = int(assetAmount)
            
            if assetAmount == 0:
                print("Asset Amount is 0")
                await message.channel.send(f"@everyone Asset Amount is 0 for {AssetName}. Unable to place order")
                return
            
            
            
            res = hlbot.place_limit_order(rawAssetName, is_buy, assetAmount, price, reduce_only)
            if res == None:
                await message.channel.send("Error placing order")
                return
            
            await message.channel.send(f"Placed limit order to {'buy' if is_buy else 'sell'} for {assetAmount} {rawAssetName}@{price}")
        
        if message.content.startswith("$tp"):
            # $tp <rawAssetName> <tp_price>
            openpositions = self.hlbot.get_all_open_positions()
            if len(openpositions) == 0:
                await message.channel.send("No open positions")
                return
            
            args = message.content.split(" ")
            if len(args) != 3:
                await message.channel.send("Invalid arguments\nUsage: $tp <rawAssetName> <tp_price>")
                return
            
            rawAssetName = args[1].upper()
            tp_price = float(args[2])
            
            AssetName = self.hlbot.get_asset_name(rawAssetName)
            tp_price = self.hlbot.get_correct_price(AssetName, tp_price)
            openpositions = self.hlbot.get_all_open_positions()
            for pos in openpositions:
                print(pos)
                if pos["position"]["coin"] == AssetName:
                    assetAmount = float(pos["position"]["szi"])
                    side = assetAmount > 0
                    self.hlbot.set_tp(AssetName, tp_price, abs(assetAmount), not side)
                    
                    break
        
        
        if message.content.startswith("$sl"):
            # $sl <rawAssetName> <sl_price>
            # openpositions = self.hlbot.get_all_open_positions()
            # if len(openpositions) == 0:
            #     await message.channel.send("No open positions")
            #     return
            
            args = message.content.split(" ")
            if len(args) != 3:
                await message.channel.send("Invalid arguments\nUsage: $sl <rawAssetName> <sl_price>")
                return
            
            rawAssetName = args[1].upper()
            sl_price = float(args[2])
            
            AssetName = self.hlbot.get_asset_name(rawAssetName)
            sl_price = self.hlbot.get_correct_price(AssetName, sl_price)
            
            openpositions = self.hlbot.get_all_open_positions()
            for pos in openpositions:
                print(pos)
                if pos["position"]["coin"] == AssetName:
                    assetAmount = float(pos["position"]["szi"])
                    side = assetAmount > 0
                    self.hlbot.set_sl(AssetName, sl_price, abs(assetAmount), not side)
                    
                    break
                    
        
        if message.content.startswith("$cancel"):
            # $cancel <rawAssetName> <oid : Optional>
            args = message.content.split(" ")
            if len(args) < 2:
                await message.channel.send("Invalid arguments\nUsage: $cancel <rawAssetName> <oid : Optional>")
                return
            
            
            if len(args) == 2:
                asset = args[1]
                hlbot = self.hlbot
                res = hlbot.cancel_all_orders(asset)
                return
            
            if len(args) == 3:
                asset = args[1]
                oid = args[2]
                hlbot = self.hlbot
                res = hlbot.cancel_limit_order(asset, oid) #messages are sent in the function
                return        
        
        if message.content.startswith("$add"):
            # $add <rawAssetName> <tf> <type : hma/ma> <length> <usdt_size> <leverage> <is_long>
            print("inside add")
            args = message.content.split(" ")
            usage = "Usage: $add <rawAssetName> <tf> <type : hma/ma> <length> <usdt_size> <leverage> <is_long>"

            if len(args) != 8:
                await message.channel.send(f"Invalid arguments\n{usage}")
                return

            try:
                asset = args[1].upper()
                tf = args[2].lower()
                stratType = args[3].lower()
                length = int(args[4])
                size = float(args[5])
                leverage = int(args[6])
                is_long = True if args[7] == "1" else False
            except:
                await message.channel.send(f"Invalid arguments\n{usage}")
                return

            if stratType == "sma":
                stratType = "ma"

            if stratType not in STRAT_TYPES:
                await message.channel.send(f"Invalid strategy type '{args[3]}'. Use one of: {', '.join(STRAT_TYPES)}")
                return

            if tf not in SUPPORTED_TFS:
                await message.channel.send(f"Invalid timeframe '{tf}'. Use one of: {', '.join(SUPPORTED_TFS)}")
                return

            if length <= 0 or length > MAX_INDICATOR_LENGTH:
                await message.channel.send(f"Length must be between 1 and {MAX_INDICATOR_LENGTH}")
                return

            self.screener.addAsset(asset, tf, length, size, leverage, is_long, stratType)

            await message.channel.send(f"Added {asset} {tf} {stratType.upper()} {length}")
            msg = self.get_assetListMsg()
            await message.channel.send(msg)
            
        if message.content.startswith("$remove"):
            # $remove <id>
            args = message.content.split(" ")
            if len(args) != 2:
                await message.channel.send("Invalid arguments\nUsage: $remove <id>")
                return
            
            id = int(args[1])
            self.screener.removeAsset(id)
            await message.channel.send(f"Removed {id}")
            
            msg = self.get_assetListMsg()
            await message.channel.send(msg)
        
        if message.content.startswith("$list"):
            msg = self.get_assetListMsg()
            await message.channel.send(msg)
            
        
        if message.content.startswith("$open"):
            # $open
            hlbot = self.hlbot
            
            msg = hlbot.get_all_open_positions()
            pretty_msg = json.dumps(msg, indent=4)
            chunks = [pretty_msg[i:i+1800] for i in range(0, len(pretty_msg), 1800)]
            for chunk in chunks:
                await asyncio.sleep(0.1) 
                await message.channel.send("```json\n Open Positions" + chunk + "```")      
            
            openorders = hlbot.get_all_open_orders()
            pretty_msg = json.dumps(openorders, indent=4)
            chunks = [pretty_msg[i:i+1800] for i in range(0, len(pretty_msg), 1800)]
            for chunk in chunks:
                await asyncio.sleep(0.1)
                await message.channel.send("```json\n Open Orders" + chunk + "```")
            
            marginsummary = hlbot.get_margin_summary()
            await asyncio.sleep(0.1) # to prevent rate limit
            marginsummary = json.dumps(marginsummary, indent=4)
            await message.channel.send("```json\n" + marginsummary + "```")      
        
        
        if message.content.startswith("$lev"):
            # $lev <rawAssetName> <lev>
            args = message.content.split(" ")
            if len(args) != 3:
                await message.channel.send("Invalid arguments\nUsage: $lev <rawAssetName> <lev>")
                return
            
            rawAssetName = None
            lev = None
            try:
                rawAssetName = args[1]
                lev = int(args[2])
            except:
                await message.channel.send("Invalid arguments")
                return
            
            hlbot = self.hlbot
            hlbot.set_leverage(rawAssetName, lev)
            
            
        
        if message.content.startswith("$amt"):
            # $amt <id> <amount>
            args = message.content.split(" ")
            if len(args) != 3:
                await message.channel.send("Invalid arguments\nUsage: $amt <id> <amount>")
                return
            
            id = None
            amount = None
            try:
                id = int(args[1])
                amount = float(args[2])
            except:
                await message.channel.send("Invalid arguments")
                return
            
            for a in self.screener.assets:
                if a.id == id:
                    a.change_txn_amount(amount)
                    await message.channel.send(f"Set Ape Size for {a.id} {a.coinpair} to {amount}")
                    return
                
            await message.channel.send("Invalid ID")
        
        
        if message.content.startswith("$dec"):
            # $dec <rawAssetName>
            args = message.content.split(" ")
            if len(args) != 2:
                await message.channel.send("Invalid arguments\nUsage: $dec <rawAssetName>")
                return
            
            asset = args[1].upper()
            hlbot = self.hlbot
            res = hlbot.get_decimals_forAsset(asset)
            if res == None:
                await message.channel.send("Invalid asset")
                return
            
            await message.channel.send(f"Decimals for {asset} is {res}")
        
        if message.content.startswith("$closeall"):
            try:
                hlbot = self.hlbot
                hlbot.close_all_positions()
            except:
                await message.channel.send("Error closing all positions")
                return
            
            await message.channel.send("Closed all positions")
            return # prevent sending the message below of $close 
                
        
        if message.content.startswith("$close"):
            # $close <rawAssetname>
            args = message.content.split(" ")
            if len(args) != 2:
                await message.channel.send("Invalid arguments\nUsage: $close <rawAssetName>")
                return
            
            asset = args[1].upper()
            hlbot = self.hlbot
            hlbot.close_position(asset)
            await message.channel.send(f"Closed {asset}")
            
            
        if message.content.startswith("$help"):
            await message.channel.send("""```Manual Trading:
$long <rawAssetName> <usdt_size> <leverage>
$short <rawAssetName> <usdt_size> <leverage>
$limit <rawAssetName> <is_buy : 1/0> <assetAsmount> <price> <reduce_only:1/0=0>
$sl <rawAssetName> <sl_price>
$cancel <rawAssetName> <oid>
$lev <rawAssetName> <lev>
$dec <rawAssetName>
$close <rawAssetName>
$closeall

Automated Trading:
$add <rawAssetName> <tf> <type : hma/ma> <length> <usdt_size> <leverage> <is_long>
$remove <id>
$amt <id> <usdt_size>

Others:
$list #for strategy list
$open #for open positions```""")
            
            
    async def send_message(self, message):
        await self.get_channel(1229113167788118096).send("@everyone " + message)