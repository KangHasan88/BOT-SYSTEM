from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SymbolMetadata:
    symbol: str
    base_asset: str
    quote_asset: str
    min_notional: float
    price_precision: int
    quantity_precision: int
    taker_fee_pct: float
    maker_fee_pct: float
    source: str = "unknown"

    def validate_order_notional(self, notional: float) -> None:
        if notional < self.min_notional:
            raise ValueError(
                f"order notional {notional} is below min_notional {self.min_notional}"
            )


@dataclass(frozen=True)
class TickerSnapshot:
    symbol: str
    captured_at_ms: int
    bid: float
    ask: float
    source: str = "unknown"

    @property
    def captured_at(self) -> datetime:
        return datetime.fromtimestamp(self.captured_at_ms / 1000, tz=timezone.utc)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_pct(self) -> float:
        return (self.spread / self.mid) * 100

    def validate(self) -> None:
        if not self.symbol:
            raise ValueError("symbol is required")
        if self.captured_at_ms <= 0:
            raise ValueError("captured_at_ms must be positive")
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("bid and ask must be positive")
        if self.ask < self.bid:
            raise ValueError("ask must be >= bid")


@dataclass(frozen=True)
class OrderBookSnapshot:
    symbol: str
    captured_at_ms: int
    best_bid: float
    best_ask: float
    bid_notional_top: float
    ask_notional_top: float
    source: str = "unknown"

    @property
    def imbalance_ratio(self) -> float:
        total = self.bid_notional_top + self.ask_notional_top
        if total == 0:
            return 0.0
        return (self.bid_notional_top - self.ask_notional_top) / total
