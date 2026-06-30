from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, order=True)
class Candle:
    symbol: str
    timeframe: str
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time_ms: int | None = None
    source: str = "unknown"

    @property
    def open_time(self) -> datetime:
        return datetime.fromtimestamp(self.open_time_ms / 1000, tz=timezone.utc)

    def key(self) -> tuple[str, str, int]:
        return (self.symbol, self.timeframe, self.open_time_ms)

    def validate(self) -> None:
        if not self.symbol:
            raise ValueError("symbol is required")
        if not self.timeframe:
            raise ValueError("timeframe is required")
        if self.open_time_ms <= 0:
            raise ValueError("open_time_ms must be positive")
        if self.high < self.low:
            raise ValueError("high must be >= low")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("prices must be positive")
        if self.volume < 0:
            raise ValueError("volume must be >= 0")


@dataclass(frozen=True)
class Gap:
    symbol: str
    timeframe: str
    missing_open_time_ms: int
    previous_open_time_ms: int
    next_open_time_ms: int


@dataclass(frozen=True)
class SyncResult:
    symbol: str
    timeframe: str
    fetched: int
    inserted_or_updated: int
    total_after_sync: int


@dataclass(frozen=True)
class QualityReport:
    symbol: str
    timeframe: str
    candle_count: int
    first_open_time_ms: int | None
    last_open_time_ms: int | None
    gap_count: int
    duplicate_count: int
    zero_volume_count: int
    non_positive_price_count: int
    dataset_id: str
