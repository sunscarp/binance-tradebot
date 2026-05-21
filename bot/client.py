"""Binance Futures Testnet client wrapper.

Handles authentication (HMAC-SHA256 signatures), HTTP request/response
lifecycle, and structured error propagation.
"""
import hashlib
import hmac
import logging
import os
import time
from typing import Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://testnet.binancefuture.com"


class BinanceAPIError(Exception):
    """Raised when Binance returns a non-2xx response or an error payload."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceFuturesClient:
    """Thin wrapper around the Binance USDT-M Futures Testnet REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: str = BASE_URL,
        timeout: int = 10,
    ):
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"X-MBX-APIKEY": self.api_key})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sign(self, params: dict) -> dict:
        """Append a HMAC-SHA256 signature to the parameter dict."""
        query = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(self, method: str, endpoint: str, signed: bool = True, **kwargs) -> dict:
        """
        Execute an HTTP request and return the parsed JSON body.

        Raises:
            BinanceAPIError: on non-2xx responses or Binance error payloads.
            requests.exceptions.RequestException: on network-level failures.
        """
        url = f"{self.base_url}{endpoint}"

        params = kwargs.pop("params", {})
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params = self._sign(params)

        logger.debug("→ %s %s  params=%s", method.upper(), endpoint, params)

        try:
            resp = self._session.request(
                method, url, params=params, timeout=self.timeout, **kwargs
            )
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network connection failed: %s", exc)
            raise
        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out after %ss: %s", self.timeout, exc)
            raise

        logger.debug("← HTTP %s  body=%s", resp.status_code, resp.text[:500])

        try:
            body = resp.json()
        except ValueError:
            resp.raise_for_status()
            raise BinanceAPIError(-1, f"Non-JSON response: {resp.text[:200]}")

        if not resp.ok:
            code = body.get("code", resp.status_code)
            msg = body.get("msg", resp.reason)
            logger.error("API error %s: %s", code, msg)
            raise BinanceAPIError(code, msg)

        return body

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_server_time(self) -> int:
        """Return Binance server time in milliseconds (connectivity check)."""
        data = self._request("GET", "/fapi/v1/time", signed=False)
        return data["serverTime"]

    def get_exchange_info(self, symbol: Optional[str] = None) -> dict:
        """Return exchange info (all symbols or a single one)."""
        params = {"symbol": symbol} if symbol else {}
        return self._request("GET", "/fapi/v1/exchangeInfo", signed=False, params=params)

    def get_account(self) -> dict:
        """Return account balances and positions."""
        return self._request("GET", "/fapi/v2/account")

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: str = "GTC",
        stop_price: Optional[float] = None,
        reduce_only: bool = False,
        duration: Optional[int] = None,
        client_algo_id: Optional[str] = None,
        position_side: Optional[str] = None,
        limit_price: Optional[float] = None,
    ) -> dict:
        """
        Place a Futures order on Binance Testnet.

        Args:
            symbol:        Trading pair, e.g. "BTCUSDT".
            side:          "BUY" or "SELL".
            order_type:    "MARKET", "LIMIT", or "STOP_MARKET".
            quantity:      Contract quantity.
            price:         Required for LIMIT orders.
            time_in_force: "GTC" | "IOC" | "FOK" (LIMIT only).
            stop_price:    Required for STOP_MARKET orders.
            reduce_only:   If True, the order only reduces an open position.

        Returns:
            dict: Raw Binance order response.

        Raises:
            BinanceAPIError: on any Binance-side rejection.
        """
        params: dict = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type == "STOP_MARKET":
            sp = stop_price if stop_price is not None else price
            if sp is None:
                raise ValueError("triggerPrice is required for STOP_MARKET orders")
            algo_params = {
                "symbol": symbol,
                "side": side,
                "algoType": "CONDITIONAL",
                "type": "STOP_MARKET",
                "quantity": quantity,
                "triggerPrice": sp,
            }
            logger.info(
                "place_algo_order → symbol=%s side=%s algoType=%s type=%s qty=%s triggerPrice=%s",
                symbol, side, "CONDITIONAL", "STOP_MARKET", quantity, sp,
            )
            response = self._request("POST", "/fapi/v1/algoOrder", params=algo_params)
            logger.info(
                "place_algo_order ← algoId=%s status=%s",
                response.get("algoId") or response.get("orderId"),
                response.get("status"),
            )
            return response

        if order_type == "TWAP":
            if duration is None:
                raise ValueError("duration is required for TWAP orders")
            algo_params = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "duration": duration,
            }
            if client_algo_id:
                algo_params["clientAlgoId"] = client_algo_id
            if position_side:
                algo_params["positionSide"] = position_side
            if limit_price is not None:
                algo_params["limitPrice"] = limit_price

            logger.info(
                "place_twap_order → symbol=%s side=%s qty=%s duration=%s positionSide=%s limitPrice=%s",
                symbol, side, quantity, duration, position_side, limit_price,
            )
            response = self._request("POST", "/sapi/v1/algo/futures/newOrderTwap", params=algo_params)
            logger.info(
                "place_twap_order ← algoId=%s status=%s",
                response.get("algoId") or response.get("orderId"),
                response.get("status"),
            )
            return response

        if order_type == "LIMIT":
            params["price"] = price
            params["timeInForce"] = time_in_force

        if order_type in ("TAKE_PROFIT_MARKET",):
            # stop_price takes precedence; fall back to price if caller used that kwarg
            sp = stop_price if stop_price is not None else price
            if sp is None:
                raise ValueError("stopPrice is required for TAKE_PROFIT_MARKET orders")
            params["stopPrice"] = sp

        if reduce_only:
            params["reduceOnly"] = "true"

        resolved_stop = params.get("stopPrice")
        logger.info(
            "place_order → symbol=%s side=%s type=%s qty=%s price=%s stopPrice=%s",
            symbol, side, order_type, quantity, price, resolved_stop,
        )

        response = self._request("POST", "/fapi/v1/order", params=params)

        logger.info(
            "place_order ← orderId=%s status=%s executedQty=%s avgPrice=%s",
            response.get("orderId"),
            response.get("status"),
            response.get("executedQty"),
            response.get("avgPrice"),
        )
        return response

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """Cancel an open order."""
        return self._request(
            "DELETE", "/fapi/v1/order", params={"symbol": symbol, "orderId": order_id}
        )

    def get_order(self, symbol: str, order_id: int) -> dict:
        """Query a single order's status."""
        return self._request(
            "GET", "/fapi/v1/order", params={"symbol": symbol, "orderId": order_id}
        )
