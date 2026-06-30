from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExchangeOrderRequest:
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None = None
    client_order_id: str | None = None


@dataclass(frozen=True)
class ExchangeOrder:
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None
    status: str
    client_order_id: str | None
    source: str


class ExecutionSafetyError(ValueError):
    """Raised when execution would violate the safety policy."""
