from __future__ import annotations

from trading_bot.data_collector.market_context import SymbolMetadata
from trading_bot.risk_manager.models import (
    AccountState,
    RiskConfig,
    RiskDecision,
    TradeCandidate,
)


def evaluate_trade_risk(
    account: AccountState,
    candidate: TradeCandidate,
    metadata: SymbolMetadata,
    config: RiskConfig | None = None,
) -> RiskDecision:
    if config is None:
        config = RiskConfig()

    reject = _hard_reject_reason(account, candidate, config)
    stop_distance = abs(candidate.entry_price - candidate.stop_price)
    stop_distance_pct = (stop_distance / candidate.entry_price) * 100 if candidate.entry_price else 0.0

    if reject:
        return _rejected(candidate, stop_distance_pct, reject)

    if candidate.side != "buy":
        return _rejected(candidate, stop_distance_pct, "v1 only supports buy candidates for spot trading")

    if candidate.entry_price <= 0 or candidate.stop_price <= 0:
        return _rejected(candidate, stop_distance_pct, "entry_price and stop_price must be positive")

    if candidate.stop_price >= candidate.entry_price:
        return _rejected(candidate, stop_distance_pct, "buy stop_price must be below entry_price")

    if stop_distance_pct < config.min_stop_distance_pct:
        return _rejected(candidate, stop_distance_pct, "stop distance too tight")

    if stop_distance_pct > config.max_stop_distance_pct:
        return _rejected(candidate, stop_distance_pct, "stop distance too wide")

    risk_pct = min(config.risk_per_trade_pct, config.max_risk_per_trade_pct)
    risk_amount = account.equity * (risk_pct / 100)
    quantity = risk_amount / stop_distance
    notional = quantity * candidate.entry_price

    try:
        metadata.validate_order_notional(notional)
    except ValueError as exc:
        return _rejected(candidate, stop_distance_pct, str(exc))

    return RiskDecision(
        status="APPROVED",
        symbol=candidate.symbol,
        side=candidate.side,
        quantity=quantity,
        notional=notional,
        risk_amount=risk_amount,
        stop_distance_pct=stop_distance_pct,
        reason=(
            f"risk approved: risk_pct={risk_pct:.2f}, risk_amount={risk_amount:.8f}, "
            f"notional={notional:.8f}"
        ),
    )


def _hard_reject_reason(
    account: AccountState,
    candidate: TradeCandidate,
    config: RiskConfig,
) -> str | None:
    if account.equity <= 0:
        return "account equity must be positive"
    if account.open_positions >= config.max_open_positions:
        return "max open positions reached"
    if account.consecutive_losses_today >= config.max_consecutive_losses_per_day:
        return "max consecutive losses reached for today"

    daily_drawdown_pct = ((account.day_start_equity - account.equity) / account.day_start_equity) * 100
    if daily_drawdown_pct >= config.daily_max_loss_pct:
        return "daily max loss reached"

    monthly_drawdown_pct = ((account.month_start_equity - account.equity) / account.month_start_equity) * 100
    if monthly_drawdown_pct >= config.monthly_max_drawdown_pct:
        return "monthly max drawdown reached"

    if candidate.confidence <= 0:
        return "candidate confidence must be positive"

    return None


def _rejected(candidate: TradeCandidate, stop_distance_pct: float, reason: str) -> RiskDecision:
    return RiskDecision(
        status="REJECTED",
        symbol=candidate.symbol,
        side=candidate.side,
        quantity=0.0,
        notional=0.0,
        risk_amount=0.0,
        stop_distance_pct=stop_distance_pct,
        reason=reason,
    )
