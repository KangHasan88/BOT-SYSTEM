from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: float = 1_000.0
    fee_pct: float = 0.10
    slippage_pct: float = 0.02
    fallback_stop_pct: float = 1.00
    atr_stop_multiplier: float = 1.5


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    timeframe: str
    entry_time_ms: int
    exit_time_ms: int
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    net_pnl: float
    exit_reason: str
    entry_signal_time_ms: int | None = None
    exit_signal_time_ms: int | None = None


@dataclass(frozen=True)
class EquityPoint:
    open_time_ms: int
    equity: float


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    timeframe: str
    initial_equity: float
    final_equity: float
    trades: list[BacktestTrade]
    equity_curve: list[EquityPoint]
    fee_pct: float = 0.0
    slippage_pct: float = 0.0
