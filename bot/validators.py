"""Input validators for CLI arguments and order parameters."""
from typing import Optional
import re

# Rough safeguards — real constraints come from exchangeInfo
MIN_QUANTITY = 0.000001
MAX_QUANTITY = 1_000_000.0
VALID_SIDES = ("BUY", "SELL")
VALID_ORDER_TYPES = ("MARKET", "LIMIT", "STOP_MARKET", "TWAP")
SYMBOL_RE = re.compile(r"^[A-Z]{2,20}$")


def validate_symbol(symbol: str) -> str:
    if not symbol or not isinstance(symbol, str):
        raise ValueError("symbol must be a non-empty string (e.g. BTCUSDT)")
    symbol = symbol.strip().upper()
    if not SYMBOL_RE.match(symbol):
        raise ValueError(
            f"symbol '{symbol}' looks invalid. Expected uppercase letters only, e.g. BTCUSDT"
        )
    return symbol


def validate_side(side: str) -> str:
    side = (side or "").strip().upper()
    if side not in VALID_SIDES:
        raise ValueError(f"side must be one of {VALID_SIDES}, got '{side}'")
    return side


def validate_order_type(order_type: str) -> str:
    order_type = (order_type or "").strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"order_type must be one of {VALID_ORDER_TYPES}, got '{order_type}'"
        )
    return order_type


def validate_quantity(quantity) -> float:
    try:
        qty = float(quantity)
    except (TypeError, ValueError):
        raise ValueError(f"quantity must be a number, got '{quantity}'")
    if qty <= 0:
        raise ValueError(f"quantity must be > 0, got {qty}")
    if qty > MAX_QUANTITY:
        raise ValueError(f"quantity {qty} exceeds maximum allowed ({MAX_QUANTITY})")
    return qty


def validate_price(price, order_type: str) -> Optional[float]:
    if order_type == "LIMIT":
        if price is None:
            raise ValueError("price is required for LIMIT orders")
        try:
            p = float(price)
        except (TypeError, ValueError):
            raise ValueError(f"price must be a number, got '{price}'")
        if p <= 0:
            raise ValueError(f"price must be > 0, got {p}")
        return p

    if order_type == "STOP_MARKET":
        if price is None:
            raise ValueError("triggerPrice is required for STOP_MARKET orders")
        try:
            p = float(price)
        except (TypeError, ValueError):
            raise ValueError(f"stop price must be a number, got '{price}'")
        if p <= 0:
            raise ValueError(f"stop price must be > 0, got {p}")
        return p

    # MARKET orders: price is ignored
    return None


def validate_twap_params(duration) -> int:
    if duration is None:
        raise ValueError("duration is required for TWAP orders")
    try:
        dur = int(duration)
    except (TypeError, ValueError):
        raise ValueError(f"duration must be an integer number of seconds, got '{duration}'")
    if dur < 300 or dur > 86400:
        raise ValueError("duration must be between 300 and 86400 seconds")
    return dur


def validate_order_input(
    symbol: str,
    side: str,
    order_type: str,
    quantity,
    price=None,
    duration=None,
    client_algo_id: Optional[str] = None,
    position_side: Optional[str] = None,
    limit_price: Optional[float] = None,
) -> dict:
    """
    Validate and normalise all order parameters.

    Returns a dict of cleaned values ready to pass to the client.
    Raises ValueError with a descriptive message on any invalid input.
    """
    clean_symbol = validate_symbol(symbol)
    clean_side = validate_side(side)
    clean_type = validate_order_type(order_type)
    clean_qty = validate_quantity(quantity)
    clean_price = validate_price(price, clean_type)

    clean_duration = None
    if clean_type == "TWAP":
        clean_duration = validate_twap_params(duration)

    clean_position_side = None
    if position_side is not None:
        ps = position_side.strip().upper()
        if ps not in ("LONG", "SHORT"):
            raise ValueError("position_side must be LONG or SHORT")
        clean_position_side = ps

    clean_limit_price = None
    if limit_price is not None:
        try:
            lp = float(limit_price)
        except (TypeError, ValueError):
            raise ValueError(f"limitPrice must be a number, got '{limit_price}'")
        if lp <= 0:
            raise ValueError(f"limitPrice must be > 0, got {lp}")
        clean_limit_price = lp

    return {
        "symbol": clean_symbol,
        "side": clean_side,
        "order_type": clean_type,
        "quantity": clean_qty,
        "price": clean_price,
        "duration": clean_duration,
        "client_algo_id": client_algo_id,
        "position_side": clean_position_side,
        "limit_price": clean_limit_price,
    }
