from __future__ import annotations

from itertools import count

from trading_bot.execution.models import ExchangeOrder, ExchangeOrderRequest, ExecutionSafetyError


class SandboxExchangeAdapter:
    def __init__(self, environment: str = "sandbox") -> None:
        if environment not in {"sandbox", "testnet"}:
            raise ExecutionSafetyError("v1 execution adapter only allows sandbox or testnet")
        self.environment = environment
        self._ids = count(1)
        self._orders: dict[str, ExchangeOrder] = {}

    def place_order(self, request: ExchangeOrderRequest) -> ExchangeOrder:
        _validate_request(request)
        order_id = f"{self.environment}-{next(self._ids)}"
        order = ExchangeOrder(
            order_id=order_id,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            status="OPEN" if request.order_type == "limit" else "FILLED",
            client_order_id=request.client_order_id,
            source=self.environment,
        )
        self._orders[order.order_id] = order
        return order

    def query_order(self, order_id: str) -> ExchangeOrder:
        try:
            return self._orders[order_id]
        except KeyError as exc:
            raise KeyError(f"order not found: {order_id}") from exc

    def cancel_order(self, order_id: str) -> ExchangeOrder:
        order = self.query_order(order_id)
        if order.status == "FILLED":
            return order
        canceled = ExchangeOrder(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            status="CANCELED",
            client_order_id=order.client_order_id,
            source=order.source,
        )
        self._orders[order_id] = canceled
        return canceled


def _validate_request(request: ExchangeOrderRequest) -> None:
    if request.symbol not in {"BTC/USDT", "ETH/USDT"}:
        raise ExecutionSafetyError("sandbox adapter only accepts BTC/USDT and ETH/USDT in v1")
    if request.side not in {"buy", "sell"}:
        raise ExecutionSafetyError("side must be buy or sell")
    if request.order_type not in {"market", "limit"}:
        raise ExecutionSafetyError("order_type must be market or limit")
    if request.quantity <= 0:
        raise ExecutionSafetyError("quantity must be positive")
    if request.order_type == "limit" and (request.price is None or request.price <= 0):
        raise ExecutionSafetyError("limit order requires positive price")
