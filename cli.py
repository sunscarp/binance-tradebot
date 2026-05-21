#!/usr/bin/env python3
"""CLI entry point for placing orders on Binance Futures Testnet.

Usage examples
--------------
# Market buy
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

# Limit sell
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 100000

# Stop-market sell (bonus order type)
python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --price 90000

# Verbose / debug logging
python cli.py --symbol ETHUSDT --side BUY --type MARKET --quantity 0.01 --verbose
"""
import argparse
import logging
import sys

from bot.logging_config import configure_logging
from bot.orders import place, format_response
from bot.client import BinanceAPIError
import requests
from bot.validators import validate_order_input


# ─────────────────────────────────────────────────────────────────────────────
# Colour helpers (graceful fallback on Windows without colorama)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init as _cinit
    _cinit(autoreset=True)
    GREEN  = Fore.GREEN
    RED    = Fore.RED
    YELLOW = Fore.YELLOW
    CYAN   = Fore.CYAN
    RESET  = Style.RESET_ALL
except ImportError:
    GREEN = RED = YELLOW = CYAN = RESET = ""


def _ok(msg: str) -> None:
    print(f"{GREEN}✔  {msg}{RESET}")


def _err(msg: str) -> None:
    print(f"{RED}✘  {msg}{RESET}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"{CYAN}{msg}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# Argument parser
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cli.py",
        description="PrimeTrade — Binance Futures Testnet order placer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --symbol BTCUSDT --side BUY  --type MARKET     --quantity 0.001
  python cli.py --symbol BTCUSDT --side SELL --type LIMIT       --quantity 0.001 --price 100000
  python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --price 90000
        """,
    )
    p.add_argument("--symbol",   required=False,  help="Trading pair, e.g. BTCUSDT")
    p.add_argument("--side",     required=False,  choices=["BUY", "SELL"], help="Order side")
    p.add_argument(
        "--type", dest="order_type", required=False,
        choices=["MARKET", "LIMIT", "STOP_MARKET", "TWAP"],
        help="Order type (STOP_MARKET or TWAP are bonus types)",
    )
    p.add_argument("--quantity", required=False,  type=float, help="Order quantity")
    p.add_argument("--price",    type=float, default=None,
                   help="Limit price (LIMIT) or stop trigger price (STOP_MARKET)")
    p.add_argument("--duration", type=int, default=None, help="TWAP duration in seconds (300-86400)")
    p.add_argument("--client-algo-id", default=None, help="Optional clientAlgoId for TWAP")
    p.add_argument("--position-side", default=None, help="TWAP position side (LONG/SHORT) for hedge mode")
    p.add_argument("--limit-price", type=float, default=None, help="TWAP limit price (optional)")
    p.add_argument("--verbose",  action="store_true", help="Enable DEBUG-level logging")
    p.add_argument("--interactive", action="store_true", help="Interactive prompt mode")
    return p


def _prompt_loop() -> dict:
    """Prompt the user for all required fields with validation."""
    while True:
        try:
            symbol = input("Symbol (e.g. BTCUSDT): ").strip()
            side = input("Side (BUY/SELL): ").strip().upper()
            order_type = input("Type (MARKET/LIMIT/STOP_MARKET/TWAP): ").strip().upper()
            quantity = input("Quantity: ").strip()
            price = input("Price (leave blank for MARKET): ").strip() or None

            duration = None
            client_algo_id = None
            position_side = None
            limit_price = None
            if order_type == "TWAP":
                duration = input("Duration (seconds, 300-86400): ").strip()
                client_algo_id = input("Client algo id (optional): ").strip() or None
                position_side = input("Position side (LONG/SHORT, optional): ").strip() or None
                limit_price = input("Limit price (optional): ").strip() or None

            cleaned = validate_order_input(
                symbol,
                side,
                order_type,
                quantity,
                price,
                duration=duration,
                client_algo_id=client_algo_id,
                position_side=position_side,
                limit_price=limit_price,
            )
            return cleaned
        except ValueError as exc:
            _err(f"Invalid input: {exc}")
            print("Please try again.\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:  # returns exit code
    parser = build_parser()
    args = parser.parse_args()
    # If not interactive, require the core arguments
    if not args.interactive:
        missing = [
            name
            for name in ("symbol", "side", "order_type", "quantity")
            if getattr(args, name) in (None, "")
        ]
        if missing:
            parser.error(
                f"the following arguments are required: {', '.join('--' + m for m in missing)}"
            )
        if args.order_type == "TWAP" and args.duration is None:
            parser.error("the following arguments are required: --duration")

    console_level = logging.DEBUG if args.verbose else logging.INFO
    configure_logging(console_level=console_level)
    logger = logging.getLogger(__name__)

    # ── Print request summary ──────────────────────────────────────────
    # If interactive, collect values via prompts
    if args.interactive:
        vals = _prompt_loop()
        args.symbol = vals["symbol"]
        args.side = vals["side"]
        args.order_type = vals["order_type"]
        args.quantity = vals["quantity"]
        args.price = vals["price"]
        args.duration = vals["duration"]
        args.client_algo_id = vals["client_algo_id"]
        args.position_side = vals["position_side"]
        args.limit_price = vals["limit_price"]

    _info("\n─── Order Request Summary ─────────────────────────────")
    _info(f"  Symbol     : {args.symbol.upper()}")
    _info(f"  Side       : {args.side}")
    _info(f"  Type       : {args.order_type}")
    _info(f"  Quantity   : {args.quantity}")
    _info(f"  Price      : {args.price if args.price else 'N/A (MARKET)'}")
    if args.order_type == "TWAP":
        _info(f"  Duration   : {args.duration}")
        _info(f"  Position   : {args.position_side if args.position_side else 'N/A'}")
        _info(f"  LimitPrice : {args.limit_price if args.limit_price else 'N/A'}")
    _info("───────────────────────────────────────────────────────\n")

    logger.info(
        "Placing order: symbol=%s side=%s type=%s qty=%s price=%s",
        args.symbol, args.side, args.order_type, args.quantity, args.price,
    )

    # ── Place order ────────────────────────────────────────────────────
    try:
        resp = place(
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
            duration=args.duration,
            client_algo_id=args.client_algo_id,
            position_side=args.position_side,
            limit_price=args.limit_price,
        )
    except ValueError as exc:
        _err(f"Invalid input: {exc}")
        logger.error("Validation error: %s", exc)
        return 1
    except BinanceAPIError as exc:
        _err(f"Binance rejected the order — code {exc.code}: {exc.message}")
        logger.error("BinanceAPIError code=%s msg=%s", exc.code, exc.message)
        return 2
    except requests.exceptions.ConnectionError:
        _err("Network error: could not reach Binance Testnet. Check your internet connection.")
        logger.exception("ConnectionError")
        return 3
    except requests.exceptions.Timeout:
        _err("Network error: request timed out.")
        logger.exception("Timeout")
        return 3
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
        logger.exception("Unexpected error")
        return 99

    # ── Print response ─────────────────────────────────────────────────
    print()
    _ok("Order placed successfully!")
    print()
    print(format_response(resp))
    print()

    logger.info(
        "Order success: orderId=%s status=%s executedQty=%s avgPrice=%s",
        resp.get("orderId"), resp.get("status"),
        resp.get("executedQty"), resp.get("avgPrice"),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
