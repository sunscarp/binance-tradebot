"""Unit tests for validators, orders, and CLI."""
import pytest
from unittest.mock import MagicMock, patch

from bot.validators import validate_order_input
from bot.orders import place, format_response
from bot.client import BinanceAPIError


# ─────────────────────────────────────────────────────────────────────────────
# Validators
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateOrderInput:
    def test_valid_market_buy(self):
        r = validate_order_input("BTCUSDT", "BUY", "MARKET", 0.001)
        assert r == {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 0.001,
            "price": None,
            "duration": None,
            "client_algo_id": None,
            "position_side": None,
            "limit_price": None,
        }

    def test_valid_limit_sell(self):
        r = validate_order_input("ETHUSDT", "sell", "limit", "0.5", 3000.0)
        assert r["side"] == "SELL"
        assert r["order_type"] == "LIMIT"
        assert r["price"] == 3000.0

    def test_stop_market_requires_price(self):
        with pytest.raises(ValueError, match="triggerPrice"):
            validate_order_input("BTCUSDT", "SELL", "STOP_MARKET", 0.001, price=None)

    def test_limit_requires_price(self):
        with pytest.raises(ValueError, match="price is required"):
            validate_order_input("BTCUSDT", "BUY", "LIMIT", 0.001, price=None)

    def test_limit_price_must_be_positive(self):
        with pytest.raises(ValueError, match="price must be > 0"):
            validate_order_input("BTCUSDT", "BUY", "LIMIT", 0.001, price=-1)

    def test_invalid_side(self):
        with pytest.raises(ValueError, match="side must be one of"):
            validate_order_input("BTCUSDT", "LONG", "MARKET", 0.001)

    def test_invalid_order_type(self):
        with pytest.raises(ValueError, match="order_type must be one of"):
            validate_order_input("BTCUSDT", "BUY", "OCO", 0.001)

    def test_zero_quantity(self):
        with pytest.raises(ValueError, match="quantity must be > 0"):
            validate_order_input("BTCUSDT", "BUY", "MARKET", 0)

    def test_negative_quantity(self):
        with pytest.raises(ValueError, match="quantity must be > 0"):
            validate_order_input("BTCUSDT", "BUY", "MARKET", -1)

    def test_symbol_normalised_to_uppercase(self):
        r = validate_order_input("btcusdt", "BUY", "MARKET", 0.001)
        assert r["symbol"] == "BTCUSDT"

    def test_market_ignores_price(self):
        r = validate_order_input("BTCUSDT", "BUY", "MARKET", 0.001, price=99999)
        assert r["price"] is None  # price discarded for MARKET


# ─────────────────────────────────────────────────────────────────────────────
# Orders layer
# ─────────────────────────────────────────────────────────────────────────────

FAKE_RESPONSE = {
    "orderId": 999,
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "MARKET",
    "status": "FILLED",
    "origQty": "0.001",
    "executedQty": "0.001",
    "avgPrice": "65000.00",
    "price": "0",
    "timeInForce": "GTC",
    "updateTime": 1716123456789,
}


class TestPlace:
    def test_delegates_to_client(self):
        mock_client = MagicMock()
        mock_client.place_order.return_value = FAKE_RESPONSE

        result = place("BTCUSDT", "BUY", "MARKET", 0.001, client=mock_client)

        mock_client.place_order.assert_called_once_with(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=0.001,
            price=None,
            duration=None,
            client_algo_id=None,
            position_side=None,
            limit_price=None,
        )
        assert result["orderId"] == 999

    def test_raises_on_invalid_input(self):
        with pytest.raises(ValueError):
            place("BTCUSDT", "BUY", "LIMIT", 0.001)  # missing price

    def test_propagates_api_error(self):
        mock_client = MagicMock()
        mock_client.place_order.side_effect = BinanceAPIError(-1121, "Invalid symbol.")

        with pytest.raises(BinanceAPIError) as exc_info:
            place("XXXYYY", "BUY", "MARKET", 0.001, client=mock_client)

        assert exc_info.value.code == -1121


class TestFormatResponse:
    def test_all_fields_present(self):
        text = format_response(FAKE_RESPONSE)
        assert "999" in text
        assert "FILLED" in text
        assert "65000.00" in text

    def test_missing_fields_show_na(self):
        text = format_response({})
        assert "N/A" in text


# ─────────────────────────────────────────────────────────────────────────────
# Client — stop price routing
# ─────────────────────────────────────────────────────────────────────────────

class TestClientStopPriceRouting:
    """Ensure price kwarg is correctly mapped to triggerPrice for STOP_MARKET."""

    def _make_client(self, fake_response: dict):
        from bot.client import BinanceFuturesClient
        client = BinanceFuturesClient(api_key="k", api_secret="s")
        client._request = MagicMock(return_value=fake_response)
        return client

    def test_stop_market_sends_stop_price_param(self):
        fake = {"orderId": 1, "status": "NEW", "executedQty": "0", "avgPrice": "0"}
        client = self._make_client(fake)
        client.place_order("BTCUSDT", "SELL", "STOP_MARKET", 0.001, price=98000)
        call_params = client._request.call_args[1]["params"]
        assert call_params["algoType"] == "CONDITIONAL"
        assert call_params["type"] == "STOP_MARKET"
        assert "triggerPrice" in call_params
        assert call_params["triggerPrice"] == 98000
        assert "price" not in call_params

    def test_stop_market_missing_price_raises(self):
        from bot.client import BinanceFuturesClient
        client = BinanceFuturesClient(api_key="k", api_secret="s")
        with pytest.raises(ValueError, match="triggerPrice is required"):
            client.place_order("BTCUSDT", "SELL", "STOP_MARKET", 0.001, price=None)

    def test_market_does_not_send_price_param(self):
        fake = {"orderId": 2, "status": "FILLED", "executedQty": "0.001", "avgPrice": "65000"}
        client = self._make_client(fake)
        client.place_order("BTCUSDT", "BUY", "MARKET", 0.001)
        call_params = client._request.call_args[1]["params"]
        assert "price" not in call_params
        assert "stopPrice" not in call_params
