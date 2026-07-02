from __future__ import annotations

from trading_bot.data_collector.market_context import SymbolMetadata
from trading_bot.data_collector.models import Candle
from trading_bot.feature_engine import build_features, classify_regimes
from trading_bot.paper.models import (
    PaperAccountSnapshot,
    PaperConfig,
    PaperOrder,
    PaperSessionResult,
    PaperTrade,
)
from trading_bot.risk_manager import (
    AccountState,
    TradeCandidate,
    evaluate_daily_profit_lock,
    evaluate_position_lock,
    evaluate_trade_risk,
)
from trading_bot.scheduler import is_entry_allowed_at_ms
from trading_bot.strategy import generate_conservative_signals


MS_PER_DAY = 86_400_000


def run_paper_session(
    candles: list[Candle],
    metadata: SymbolMetadata,
    config: PaperConfig | None = None,
) -> PaperSessionResult:
    if config is None:
        config = PaperConfig()
    if not candles:
        return PaperSessionResult(metadata.symbol, "", config.initial_equity, config.initial_equity, [], [], [])

    ordered = sorted(candles, key=lambda candle: candle.open_time_ms)
    symbol = ordered[0].symbol
    timeframe = ordered[0].timeframe
    features = build_features(ordered)
    regimes = classify_regimes(features)
    signals = generate_conservative_signals(features, regimes)
    feature_by_time = {row.open_time_ms: row for row in features}
    signal_by_time = {signal.open_time_ms: signal for signal in signals}

    equity = config.initial_equity
    day_start_equity = config.initial_equity
    month_start_equity = config.initial_equity
    current_day = _day_bucket(ordered[0].open_time_ms)
    high_watermark = config.initial_equity
    consecutive_losses_today = 0
    trading_status = "OPEN"
    status_reason = "paper session started"
    open_position: dict[str, float | int] | None = None

    orders: list[PaperOrder] = []
    trades: list[PaperTrade] = []
    snapshots: list[PaperAccountSnapshot] = []

    for candle in ordered:
        candle_day = _day_bucket(candle.open_time_ms)
        if candle_day != current_day:
            current_day = candle_day
            day_start_equity = equity
            high_watermark = equity
            consecutive_losses_today = 0
            trading_status = "OPEN"
            status_reason = "new paper trading day"

        if open_position is not None and candle.low <= float(open_position["stop_price"]):
            equity, trade, order = _close_position(
                open_position,
                exit_time_ms=candle.open_time_ms,
                exit_price=_apply_sell_slippage(float(open_position["stop_price"]), config),
                equity=equity,
                fee_pct=config.fee_pct,
                reason="STOP_LOSS",
                symbol=symbol,
                timeframe=timeframe,
            )
            trades.append(trade)
            orders.append(order)
            consecutive_losses_today = consecutive_losses_today + 1 if trade.net_pnl < 0 else 0
            open_position = None

        lock_state = evaluate_daily_profit_lock(
            day_start_equity=day_start_equity,
            current_equity=equity,
            previous_high_watermark_equity=high_watermark,
        )
        high_watermark = lock_state.high_watermark_equity
        trading_status = lock_state.status
        status_reason = lock_state.reason

        signal = signal_by_time.get(candle.open_time_ms)
        feature = feature_by_time.get(candle.open_time_ms)

        if open_position is not None and signal is not None and signal.action == "EXIT_CANDIDATE":
            equity, trade, order = _close_position(
                open_position,
                exit_time_ms=candle.open_time_ms,
                exit_price=_apply_sell_slippage(candle.close, config),
                equity=equity,
                fee_pct=config.fee_pct,
                reason="EXIT_SIGNAL",
                symbol=symbol,
                timeframe=timeframe,
            )
            trades.append(trade)
            orders.append(order)
            consecutive_losses_today = consecutive_losses_today + 1 if trade.net_pnl < 0 else 0
            open_position = None

        if open_position is not None:
            decision = evaluate_position_lock(
                side="buy",
                entry_price=float(open_position["entry_price"]),
                stop_price=float(open_position["stop_price"]),
                current_price=candle.close,
                initial_stop_price=float(open_position["initial_stop_price"]),
            )
            if decision.should_update_stop:
                open_position["stop_price"] = decision.new_stop_price

        if (
            open_position is None
            and trading_status not in {"STOP_TRADING", "DAILY_TARGET_HIT"}
            and signal is not None
            and signal.action == "BUY_CANDIDATE"
            and feature is not None
        ):
            session_decision = is_entry_allowed_at_ms(
                candle.open_time_ms,
                config.entry_windows_wib,
                config.timezone,
            )
            if config.enforce_entry_windows and not session_decision.allowed:
                orders.append(
                    PaperOrder(
                        symbol=symbol,
                        timeframe=timeframe,
                        open_time_ms=candle.open_time_ms,
                        side="buy",
                        action="OPEN",
                        price=candle.close,
                        quantity=0.0,
                        notional=0.0,
                        fee=0.0,
                        status="REJECTED",
                        reason=session_decision.reason,
                    )
                )
                snapshots.append(
                    _account_snapshot(
                        candle_open_time_ms=candle.open_time_ms,
                        equity=equity,
                        day_start_equity=day_start_equity,
                        month_start_equity=month_start_equity,
                        open_position=None,
                        current_close=candle.close,
                        consecutive_losses_today=consecutive_losses_today,
                        trading_status=trading_status,
                        status_reason=status_reason,
                        config=config,
                    )
                )
                continue

            entry_price = _apply_buy_slippage(candle.close, config)
            stop_price = _initial_stop_price(entry_price, feature.atr, config)
            risk_decision = evaluate_trade_risk(
                account=AccountState(
                    equity=equity,
                    day_start_equity=day_start_equity,
                    month_start_equity=month_start_equity,
                    open_positions=0,
                    consecutive_losses_today=consecutive_losses_today,
                ),
                candidate=TradeCandidate(
                    symbol=symbol,
                    side="buy",
                    entry_price=entry_price,
                    stop_price=stop_price,
                    confidence=signal.confidence,
                ),
                metadata=metadata,
            )
            if risk_decision.status == "APPROVED":
                entry_fee = risk_decision.notional * (config.fee_pct / 100)
                equity -= entry_fee
                open_position = {
                    "entry_time_ms": candle.open_time_ms,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "initial_stop_price": stop_price,
                    "quantity": risk_decision.quantity,
                    "entry_fee": entry_fee,
                }
                orders.append(
                    PaperOrder(
                        symbol=symbol,
                        timeframe=timeframe,
                        open_time_ms=candle.open_time_ms,
                        side="buy",
                        action="OPEN",
                        price=entry_price,
                        quantity=risk_decision.quantity,
                        notional=risk_decision.notional,
                        fee=entry_fee,
                        status="FILLED",
                        reason=risk_decision.reason,
                    )
                )
            else:
                orders.append(
                    PaperOrder(
                        symbol=symbol,
                        timeframe=timeframe,
                        open_time_ms=candle.open_time_ms,
                        side="buy",
                        action="OPEN",
                        price=entry_price,
                        quantity=0.0,
                        notional=0.0,
                        fee=0.0,
                        status="REJECTED",
                        reason=risk_decision.reason,
                    )
                )

        snapshots.append(
            _account_snapshot(
                candle_open_time_ms=candle.open_time_ms,
                equity=equity,
                day_start_equity=day_start_equity,
                month_start_equity=month_start_equity,
                open_position=open_position,
                current_close=candle.close,
                consecutive_losses_today=consecutive_losses_today,
                trading_status=trading_status,
                status_reason=status_reason,
                config=config,
            )
        )

    if open_position is not None:
        last = ordered[-1]
        equity, trade, order = _close_position(
            open_position,
            exit_time_ms=last.open_time_ms,
            exit_price=_apply_sell_slippage(last.close, config),
            equity=equity,
            fee_pct=config.fee_pct,
            reason="SESSION_END",
            symbol=symbol,
            timeframe=timeframe,
        )
        trades.append(trade)
        orders.append(order)

    return PaperSessionResult(
        symbol=symbol,
        timeframe=timeframe,
        initial_equity=config.initial_equity,
        final_equity=equity,
        orders=orders,
        trades=trades,
        account_snapshots=snapshots,
    )


def _day_bucket(open_time_ms: int) -> int:
    return open_time_ms // MS_PER_DAY


def _initial_stop_price(entry_price: float, atr_value: float | None, config: PaperConfig) -> float:
    if atr_value is not None and atr_value > 0:
        return entry_price - (atr_value * config.atr_stop_multiplier)
    return entry_price * (1 - (config.fallback_stop_pct / 100))


def _apply_buy_slippage(price: float, config: PaperConfig) -> float:
    return price * (1 + (config.slippage_pct / 100))


def _apply_sell_slippage(price: float, config: PaperConfig) -> float:
    return price * (1 - (config.slippage_pct / 100))


def _account_snapshot(
    candle_open_time_ms: int,
    equity: float,
    day_start_equity: float,
    month_start_equity: float,
    open_position: dict[str, float | int] | None,
    current_close: float,
    consecutive_losses_today: int,
    trading_status: str,
    status_reason: str,
    config: PaperConfig,
) -> PaperAccountSnapshot:
    unrealized_pnl = _unrealized_pnl(open_position, current_close, config) if open_position is not None else 0.0
    return PaperAccountSnapshot(
        open_time_ms=candle_open_time_ms,
        equity=equity,
        day_start_equity=day_start_equity,
        month_start_equity=month_start_equity,
        open_positions=1 if open_position is not None else 0,
        consecutive_losses_today=consecutive_losses_today,
        trading_status=trading_status,
        status_reason=status_reason,
        unrealized_pnl=unrealized_pnl,
        marked_equity=equity + unrealized_pnl,
    )


def _unrealized_pnl(position: dict[str, float | int], current_close: float, config: PaperConfig) -> float:
    quantity = float(position["quantity"])
    entry_price = float(position["entry_price"])
    marked_exit_price = _apply_sell_slippage(current_close, config)
    gross_pnl = (marked_exit_price - entry_price) * quantity
    exit_fee = (marked_exit_price * quantity) * (config.fee_pct / 100)
    return gross_pnl - exit_fee


def _close_position(
    position: dict[str, float | int],
    exit_time_ms: int,
    exit_price: float,
    equity: float,
    fee_pct: float,
    reason: str,
    symbol: str,
    timeframe: str,
) -> tuple[float, PaperTrade, PaperOrder]:
    quantity = float(position["quantity"])
    entry_price = float(position["entry_price"])
    gross_pnl = (exit_price - entry_price) * quantity
    exit_fee = (exit_price * quantity) * (fee_pct / 100)
    entry_fee = float(position["entry_fee"])
    new_equity = equity + gross_pnl - exit_fee
    net_pnl = gross_pnl - entry_fee - exit_fee

    trade = PaperTrade(
        symbol=symbol,
        timeframe=timeframe,
        entry_time_ms=int(position["entry_time_ms"]),
        exit_time_ms=exit_time_ms,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        gross_pnl=gross_pnl,
        fees=entry_fee + exit_fee,
        net_pnl=net_pnl,
        exit_reason=reason,
    )
    order = PaperOrder(
        symbol=symbol,
        timeframe=timeframe,
        open_time_ms=exit_time_ms,
        side="sell",
        action="CLOSE",
        price=exit_price,
        quantity=quantity,
        notional=exit_price * quantity,
        fee=exit_fee,
        status="FILLED",
        reason=reason,
    )
    return new_equity, trade, order
