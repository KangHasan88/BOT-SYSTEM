from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    symbol: str
    timeframe: str
    open_time_ms: int
    action: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class SignalConfig:
    min_buy_rsi: float = 45.0
    max_buy_rsi: float = 70.0
    exit_rsi: float = 78.0
    min_volume_ratio: float = 0.80
    buy_regimes: tuple[str, ...] = ("trending_up",)
