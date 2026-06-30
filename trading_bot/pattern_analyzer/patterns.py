from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatternSignal:
    symbol: str
    timeframe: str
    open_time_ms: int
    pattern: str
    score: float
    reference_price: float
    reason: str


@dataclass(frozen=True)
class SwingPoint:
    symbol: str
    timeframe: str
    open_time_ms: int
    kind: str
    price: float
