# PrimeTrade — Binance Futures Testnet Trading Bot

A clean, production-structured Python CLI application that places orders on the **Binance USDT-M Futures Testnet** with full logging, input validation, and error handling.

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST client (HMAC-SHA256 auth, error handling)
│   ├── orders.py          # Order placement logic & response formatting
│   ├── validators.py      # Input validation with descriptive error messages
│   └── logging_config.py  # Rotating file + console logging
├── tests/
│   └── test_bot.py        # Unit tests (validators, orders layer)
├── logs/
│   └── trading_bot.log    # Auto-created on first run
├── cli.py                 # CLI entry point (argparse)
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet API credentials

1. Register at [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in → **API Key** tab → Generate a key pair
3. Copy your **API Key** and **Secret Key**

### 2. Clone & install

```bash
git clone https://github.com/your-username/trading_bot.git
cd trading_bot

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Set environment variables

```bash
# Windows PowerShell
$env:BINANCE_API_KEY    = "wnDZ6TGHy0D7WZmRe5pEMZjzCrPycUw8bKDt9iua5qYqtA2cU9BVZrxLaDx1GqCS"
$env:BINANCE_API_SECRET = "abLTCLOhU9AJ2q8XbS5WFsw97JDIMk2pKthOA3o99UGlP2dsq1ULwiCoHAVu7Iq6"

# macOS / Linux
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"
```

---

## Running the Bot

### Market order (BUY)
```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

### Limit order (SELL)
```bash
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 108000
```

### Stop-Market order — bonus order type (SELL, triggers at 98 000)
```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --price 98000
```

### TWAP order — bonus order type (BUY, 1 hour duration)
```bash
python cli.py --symbol BTCUSDT --side BUY --type TWAP --quantity 1.0 --duration 3600
```

### Enable debug logging
```bash
python cli.py --symbol ETHUSDT --side BUY --type MARKET --quantity 0.01 --verbose
```

### Help
```bash
python cli.py --help
```

---

## Sample Output

```
─── Order Request Summary ─────────────────────────────
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.001
  Price      : N/A (MARKET)
───────────────────────────────────────────────────────

✔  Order placed successfully!

┌─────────────────────────────────────────
│  Order ID      : 4185623
│  Symbol        : BTCUSDT
│  Side          : BUY
│  Type          : MARKET
│  Status        : FILLED
│  Orig Qty      : 0.001
│  Executed Qty  : 0.001
│  Avg Price     : 104321.50
│  Price         : 0
│  Time in Force : GTC
│  Update Time   : 1747600541387
└─────────────────────────────────────────
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Logging

Logs are written to **`logs/trading_bot.log`** (rotating, 5 MB × 3 backups) and echoed to the console.

Every order logs:
- Request parameters (symbol, side, type, qty, price)
- Raw HTTP response
- Parsed order fields (orderId, status, executedQty, avgPrice)
- Any validation or API errors

---

## Architecture

| Layer | File | Responsibility |
|-------|------|----------------|
| CLI | `cli.py` | Parse args, print output, map exceptions to exit codes |
| Orders | `bot/orders.py` | Orchestrate validation + client call; format response |
| Validators | `bot/validators.py` | Sanitise & normalise all user inputs |
| Client | `bot/client.py` | HTTP, HMAC signing, error propagation |
| Logging | `bot/logging_config.py` | Rotating file + console handlers |

### Error handling

| Exception | Source | CLI exit code |
|-----------|--------|---------------|
| `ValueError` | Invalid user input | `1` |
| `BinanceAPIError` | Binance rejects order | `2` |
| `ConnectionError` / `Timeout` | Network failure | `3` |
| Anything else | Unexpected | `99` |

---

## Supported Order Types

| Type | Notes |
|------|-------|
| `MARKET` | Executes immediately at best available price |
| `LIMIT` | Rests in the book at your specified price (`--price` required) |
| `STOP_MARKET` | *(Bonus)* Triggers a market order when price hits `--price` (placed via `algoOrder` endpoint) |
| `TWAP` | *(Bonus)* Time-weighted average price order via `/sapi/v1/algo/futures/newOrderTwap` (`--duration` required) |

---

## Assumptions

- Testnet only — `base_url` is hard-coded to `https://testnet.binancefuture.com`
- USDT-M Futures only (COIN-M not tested)
- `timeInForce` defaults to `GTC` for LIMIT orders (configurable via `orders.py`)
- Quantity precision is passed as-is; Binance will reject if it violates the symbol's `LOT_SIZE` filter — no client-side rounding is applied intentionally (keeps the code transparent)
- Credentials are supplied via environment variables (`BINANCE_API_KEY`, `BINANCE_API_SECRET`)
- `STOP_MARKET` orders are routed to the new `/fapi/v1/algoOrder` endpoint with `algoType=CONDITIONAL`, `type=STOP_MARKET`, and `triggerPrice`
- `TWAP` orders use `/sapi/v1/algo/futures/newOrderTwap` with `duration` and optional `positionSide`/`limitPrice`

---

## Requirements

- Python 3.8+
- `requests >= 2.31`
- `colorama >= 0.4.6` *(optional — coloured output gracefully degrades without it)*
