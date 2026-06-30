from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountState:
    equity: float
    day_start_equity: float
    month_start_equity: float
    open_positions: int
    consecutive_losses_today: int = 0


@dataclass(frozen=True)
class TradeCandidate:
    symbol: str
    side: str
    entry_price: float
    stop_price: float
    confidence: float


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade_pct: float = 0.25
    max_risk_per_trade_pct: float = 0.50
    daily_max_loss_pct: float = 1.00
    monthly_max_drawdown_pct: float = 5.00
    max_open_positions: int = 1
    max_consecutive_losses_per_day: int = 2
    min_stop_distance_pct: float = 0.10
    max_stop_distance_pct: float = 3.00


@dataclass(frozen=True)
class RiskDecision:
    status: str
    symbol: str
    side: str
    quantity: float
    notional: float
    risk_amount: float
    stop_distance_pct: float
    reason: str
