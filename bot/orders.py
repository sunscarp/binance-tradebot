"""Order placement logic — sits between CLI and the raw client."""
import logging
from typing import Optional

from .client import BinanceFuturesClient, BinanceAPIError
from .validators import validate_order_input

logger = logging.getLogger(__name__)


def place(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
    duration: Optional[int] = None,
    client_algo_id: Optional[str] = None,
    position_side: Optional[str] = None,
    limit_price: Optional[float] = None,
    client: Optional[BinanceFuturesClient] = None,
) -> dict:
    """
    Validate inputs and place an order via the Binance Futures client.

    Args:
        symbol:     Trading pair (e.g. "BTCUSDT").
        side:       "BUY" or "SELL".
        order_type: "MARKET", "LIMIT", or "STOP_MARKET".
        quantity:   Contract quantity.
        price:      Price for LIMIT / stop price for STOP_MARKET.
        client:     Optional pre-built client (useful for testing/DI).

    Returns:
        dict: Binance order response.

    Raises:
        ValueError:       On invalid input parameters.
        BinanceAPIError:  On Binance-side rejection.
        requests.exceptions.*: On network failures.
    """
    # 1. Validate & normalise
    params = validate_order_input(
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
    logger.info("Order validated: %s", params)

    # 2. Build client if not injected
    client = client or BinanceFuturesClient()

    # 3. Place
    resp = client.place_order(**params)
    logger.debug("Raw order response: %s", resp)
    return resp


def format_response(resp: dict) -> str:
    """Return a human-readable summary of a Binance order response."""
    lines = [
        "┌─────────────────────────────────────────",
            f"│  Order ID      : {resp.get('orderId', 'N/A')}",
            f"│  Algo ID       : {resp.get('algoId', 'N/A')}",
        f"│  Client Algo ID: {resp.get('clientAlgoId', 'N/A')}",
        f"│  Symbol        : {resp.get('symbol', 'N/A')}",
        f"│  Side          : {resp.get('side', 'N/A')}",
            f"│  Type          : {resp.get('type', resp.get('algoType', 'N/A'))}",
        f"│  Status        : {resp.get('status', 'N/A')}",
        f"│  Orig Qty      : {resp.get('origQty', 'N/A')}",
        f"│  Executed Qty  : {resp.get('executedQty', 'N/A')}",
        f"│  Avg Price     : {resp.get('avgPrice', 'N/A')}",
        f"│  Price         : {resp.get('price', 'N/A')}",
        f"│  Time in Force : {resp.get('timeInForce', 'N/A')}",
        f"│  Update Time   : {resp.get('updateTime', 'N/A')}",
        "└─────────────────────────────────────────",
    ]
    return "\n".join(lines)
