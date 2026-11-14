# Hyperliquid Trading Bot

This bot is designed to automate and streamline your trading experience on Hyperliquid(a decentralized perpetuals exchange) offering both manual and automated trading capabilities.

# Features
## Manual Trading
 - **Trade Execution:** Execute long and short trades swiftly with precise control over asset selection, trade size, and leverage.
 - **Efficient Order Management:** Place limit orders, set stop-loss levels, and manage or cancel orders with ease.
 - **Enhanced Speed:** Faster Experience lower latency and faster order placements compared to manual UI-based trading.

## Automated Trading
- **Strategy Automation:** Automate a trading strategy with detailed control over parameters like assets, timeframes, leverage, and moving averages. Two strategies are available: the [Hull Suite](https://www.tradingview.com/script/hg92pFwS-Hull-Suite/) HMA slope strategy, and a simple moving average (SMA) crossover strategy.
- **Reduced Human Error:** Removes the influence of human emotions and the need to constantly monitor charts, leading to more consistent and reliable trading outcomes.
- **Live Alerts:** Receive instant notifications via discord webhook whenever a position is opened or closed, keeping you continuously informed about your trading activities.

# Commands

| **Command**   | **Usage**                                                                                                               | **Description**                                                                                           |
|---------------|-------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| `$long`       | `$long <rawAssetName> <usdt_size> <leverage>`                                                                          | Execute a long trade with the specified asset, trade size, and leverage.                                  |
| `$short`      | `$short <rawAssetName> <usdt_size> <leverage>`                                                                         | Execute a short trade with the specified asset, trade size, and leverage.                                 |
| `$limit`      | `$limit <rawAssetName> <is_buy : 1/0> <assetAmount> <price> <reduce_only:1/0>`                                        | Place a limit order for the specified asset with the option to buy/sell, amount, price, and reduce-only setting. |
| `$sl`         | `$sl <rawAssetName> <sl_price>`                                                                                        | Set a stop-loss order for the specified asset with the given stop-loss price.                             |
| `$cancel`     | `$cancel <rawAssetName> <oid>`                                                                                        | Cancel an existing order for the specified asset using the order ID.                                       |
| `$lev`        | `$lev <rawAssetName> <lev>`                                                                                             | Adjust the leverage for the specified asset to the given level.                                            |                                                                                                  | Decrease the leverage for the specified asset.                                                            |
| `$close`      | `$close <rawAssetName>`                                                                                                 | Close the position for the specified asset.                                                               |
| `$closeall`   | `$closeall`                                                                                                            | Close all open positions.                                                                                 |
| `$add`        | `$add <rawAssetName> <tf> <type : hma/ma> <length> <usdt_size> <leverage> <is_long>`                                   | Add an automated trading strategy for the specified asset. `type` selects HMA (slope flip) or MA/SMA (price crosses the MA). Remaining params: timeframe, indicator length, trade size, leverage, and direction. |
| `$remove`     | `$remove <id>`                                                                                                         | Remove an automated trading strategy by its ID.                                                            |
| `$amt`        | `$amt <id> <usdt_size>`                                                                                               | Adjust the trade size for the strategy with the specified ID.                                             |
| `$list`       | `$list`                                                                                                                | List all active trading strategies.                                                                       |
| `$open`       | `$open`                                                                                                                | Display all open positions and orders.                                                                              |

## Examples
- To place a $1000 BTC Long on 3x leverage
```shell
$long btc 1000 3
```

- To start a new long-only strategy on BTC on the 4H timeframe with each order being worth $3000 using 2x leverage, using the HMA strategy with a length of 34
```shell
$add btc 4h hma 34 3000 2 1
```

- Same idea, but using a 50-period SMA and going long when price closes above it
```shell
$add btc 4h ma 50 3000 2 1
```


# Getting Started

1. Clone the Repo
```shell
git clone https://github.com/Sakaar-Sen/Hyperliquid-Trading-Bot
```

2. Install Dependencies. Requires Python 3.11 or newer.
```bash
pip install -r requirements.txt
```

3. Configure the settings in ```config_example.json```. Skip the `secret_key` key for now.

4. Run `encryptSecretKey.py` and input the private key of your wallet and a password. This password will be used to initialize the bot using the command `$start <password>` when it runs. 

5. Run `main.py` to start the bot. Use `$help` to view the list of all commands.

# How does it work?
<img width="1889" alt="hlBot Diagram" src="https://github.com/user-attachments/assets/1700eb13-928c-48ee-87a0-8bce5f1cd6a0">

# Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.


