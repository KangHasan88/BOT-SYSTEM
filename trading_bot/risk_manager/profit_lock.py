from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DailyProfitLockConfig:
    trigger_pct: float = 0.50
    lock_ratio: float = 0.60
    daily_target_pct: float = 1.00


@dataclass(frozen=True)
class DailyProfitLockState:
    day_start_equity: float
    current_equity: float
    high_watermark_equity: float
    lock_active: bool
    floor_equity: float | None
    status: str
    reason: str


@dataclass(frozen=True)
class PositionLockConfig:
    break_even_at_r: float = 1.0
    lock_profit_at_r: float = 1.5
    lock_profit_ratio: float = 0.25


@dataclass(frozen=True)
class PositionLockDecision:
    should_update_stop: bool
    new_stop_price: float
    reason: str


def evaluate_daily_profit_lock(
    day_start_equity: float,
    current_equity: float,
    previous_high_watermark_equity: float | None = None,
    config: DailyProfitLockConfig | None = None,
) -> DailyProfitLockState:
    if config is None:
        config = DailyProfitLockConfig()
    if day_start_equity <= 0:
        raise ValueError("day_start_equity must be positive")

    high_watermark = max(previous_high_watermark_equity or day_start_equity, current_equity)
    profit_pct = ((current_equity - day_start_equity) / day_start_equity) * 100
    high_profit_pct = ((high_watermark - day_start_equity) / day_start_equity) * 100

    lock_active = high_profit_pct >= config.trigger_pct
    floor_equity = None
    status = "OPEN"
    reason = "profit lock not active"

    if lock_active:
        locked_profit = (high_watermark - day_start_equity) * config.lock_ratio
        floor_equity = day_start_equity + locked_profit
        status = "LOCK_ACTIVE"
        reason = (
            f"profit lock active: high_profit_pct={high_profit_pct:.4f}, "
            f"floor_equity={floor_equity:.8f}"
        )

        if current_equity <= floor_equity:
            status = "STOP_TRADING"
            reason = "current equity reached daily profit floor"

    if profit_pct >= config.daily_target_pct:
        status = "DAILY_TARGET_HIT"
        reason = "daily target reached"

    return DailyProfitLockState(
        day_start_equity=day_start_equity,
        current_equity=current_equity,
        high_watermark_equity=high_watermark,
        lock_active=lock_active,
        floor_equity=floor_equity,
        status=status,
        reason=reason,
    )


def evaluate_position_lock(
    side: str,
    entry_price: float,
    stop_price: float,
    current_price: float,
    config: PositionLockConfig | None = None,
    initial_stop_price: float | None = None,
) -> PositionLockDecision:
    if config is None:
        config = PositionLockConfig()
    if side != "buy":
        return PositionLockDecision(False, stop_price, "v1 position lock only supports buy side")
    if entry_price <= 0 or stop_price <= 0 or current_price <= 0:
        raise ValueError("prices must be positive")
    initial_stop = initial_stop_price if initial_stop_price is not None else stop_price
    if initial_stop >= entry_price:
        if stop_price >= entry_price:
            return PositionLockDecision(False, stop_price, "stop already at or above break-even")
        raise ValueError("buy initial_stop_price must be below entry_price")

    initial_risk = entry_price - initial_stop
    current_r = (current_price - entry_price) / initial_risk

    if current_r >= config.lock_profit_at_r:
        locked_stop = entry_price + (initial_risk * config.lock_profit_ratio)
        return PositionLockDecision(
            should_update_stop=locked_stop > stop_price,
            new_stop_price=max(stop_price, locked_stop),
            reason=f"lock profit after {current_r:.2f}R",
        )

    if current_r >= config.break_even_at_r:
        return PositionLockDecision(
            should_update_stop=entry_price > stop_price,
            new_stop_price=max(stop_price, entry_price),
            reason=f"move stop to break-even after {current_r:.2f}R",
        )

    return PositionLockDecision(False, stop_price, f"position profit only {current_r:.2f}R")
