from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperConfig:
    initial_equity: float = 1_000.0
    fee_pct: float = 0.10
    slippage_pct: float = 0.02
    fallback_stop_pct: float = 1.00
    atr_stop_multiplier: float = 1.5
    entry_windows_wib: tuple[str, ...] = ("08:00-11:00", "19:00-23:30")
    timezone: str = "Asia/Jakarta"
    enforce_entry_windows: bool = True


@dataclass(frozen=True)
class PaperOrder:
    symbol: str
    timeframe: str
    open_time_ms: int
    side: str
    action: str
    price: float
    quantity: float
    notional: float
    fee: float
    status: str
    reason: str


@dataclass(frozen=True)
class PaperTrade:
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


@dataclass(frozen=True)
class PaperAccountSnapshot:
    open_time_ms: int
    equity: float
    day_start_equity: float
    month_start_equity: float
    open_positions: int
    consecutive_losses_today: int
    trading_status: str
    status_reason: str
    unrealized_pnl: float = 0.0
    marked_equity: float = 0.0


@dataclass(frozen=True)
class PaperSessionResult:
    symbol: str
    timeframe: str
    initial_equity: float
    final_equity: float
    orders: list[PaperOrder]
    trades: list[PaperTrade]
    account_snapshots: list[PaperAccountSnapshot]
