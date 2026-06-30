from __future__ import annotations

from trading_bot.backtest.models import BacktestConfig, BacktestResult, BacktestTrade, EquityPoint
from trading_bot.data_collector.market_context import SymbolMetadata
from trading_bot.data_collector.models import Candle
from trading_bot.feature_engine import build_features, classify_regimes
from trading_bot.risk_manager import AccountState, TradeCandidate, evaluate_position_lock, evaluate_trade_risk
from trading_bot.strategy import generate_conservative_signals


def run_event_backtest(
    candles: list[Candle],
    metadata: SymbolMetadata,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    if config is None:
        config = BacktestConfig()
    if not candles:
        symbol = metadata.symbol
        return BacktestResult(
            symbol,
            "",
            config.initial_equity,
            config.initial_equity,
            [],
            [],
            fee_pct=config.fee_pct,
            slippage_pct=config.slippage_pct,
        )

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
    open_position: dict[str, float | int] | None = None
    pending_entry: dict[str, float | int] | None = None
    pending_exit_signal_time_ms: int | None = None
    trades: list[BacktestTrade] = []
    equity_curve: list[EquityPoint] = []

    for candle in ordered:
        if open_position is not None:
            stop_price = float(open_position["stop_price"])
            if candle.low <= stop_price:
                equity, trade = _close_position(
                    open_position,
                    exit_time_ms=candle.open_time_ms,
                    exit_price=_apply_sell_slippage(stop_price, config),
                    equity=equity,
                    fee_pct=config.fee_pct,
                    reason="STOP_LOSS",
                    symbol=symbol,
                    timeframe=timeframe,
                    exit_signal_time_ms=None,
                )
                trades.append(trade)
                open_position = None

        if open_position is not None and pending_exit_signal_time_ms is not None:
            equity, trade = _close_position(
                open_position,
                exit_time_ms=candle.open_time_ms,
                exit_price=_apply_sell_slippage(candle.open, config),
                equity=equity,
                fee_pct=config.fee_pct,
                reason="EXIT_SIGNAL",
                symbol=symbol,
                timeframe=timeframe,
                exit_signal_time_ms=pending_exit_signal_time_ms,
            )
            trades.append(trade)
            open_position = None
            pending_exit_signal_time_ms = None

        if open_position is None and pending_entry is not None:
            entry_price = _apply_buy_slippage(candle.open, config)
            atr_value = pending_entry.get("atr")
            stop_price = _initial_stop_price(
                entry_price,
                float(atr_value) if atr_value is not None else None,
                config,
            )
            risk_decision = evaluate_trade_risk(
                account=AccountState(
                    equity=equity,
                    day_start_equity=day_start_equity,
                    month_start_equity=month_start_equity,
                    open_positions=0,
                ),
                candidate=TradeCandidate(
                    symbol=symbol,
                    side="buy",
                    entry_price=entry_price,
                    stop_price=stop_price,
                    confidence=float(pending_entry["confidence"]),
                ),
                metadata=metadata,
            )
            if risk_decision.status == "APPROVED":
                entry_fee = risk_decision.notional * (config.fee_pct / 100)
                equity -= entry_fee
                open_position = {
                    "entry_time_ms": candle.open_time_ms,
                    "entry_signal_time_ms": int(pending_entry["signal_time_ms"]),
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "initial_stop_price": stop_price,
                    "quantity": risk_decision.quantity,
                    "entry_fee": entry_fee,
                }
            pending_entry = None

        signal = signal_by_time.get(candle.open_time_ms)
        feature = feature_by_time.get(candle.open_time_ms)

        if open_position is not None and signal is not None and signal.action == "EXIT_CANDIDATE":
            pending_exit_signal_time_ms = candle.open_time_ms

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
            and signal is not None
            and signal.action == "BUY_CANDIDATE"
            and feature is not None
        ):
            pending_entry = {
                "signal_time_ms": candle.open_time_ms,
                "atr": feature.atr,
                "confidence": signal.confidence,
            }

        equity_curve.append(EquityPoint(candle.open_time_ms, equity))

    if open_position is not None:
        last = ordered[-1]
        equity, trade = _close_position(
            open_position,
            exit_time_ms=last.open_time_ms,
            exit_price=_apply_sell_slippage(last.close, config),
            equity=equity,
            fee_pct=config.fee_pct,
            reason="END_OF_DATA",
            symbol=symbol,
            timeframe=timeframe,
            exit_signal_time_ms=None,
        )
        trades.append(trade)
        equity_curve.append(EquityPoint(last.open_time_ms, equity))

    return BacktestResult(
        symbol=symbol,
        timeframe=timeframe,
        initial_equity=config.initial_equity,
        final_equity=equity,
        trades=trades,
        equity_curve=equity_curve,
        fee_pct=config.fee_pct,
        slippage_pct=config.slippage_pct,
    )


def _initial_stop_price(entry_price: float, atr_value: float | None, config: BacktestConfig) -> float:
    if atr_value is not None and atr_value > 0:
        return entry_price - (atr_value * config.atr_stop_multiplier)
    return entry_price * (1 - (config.fallback_stop_pct / 100))


def _apply_buy_slippage(price: float, config: BacktestConfig) -> float:
    return price * (1 + (config.slippage_pct / 100))


def _apply_sell_slippage(price: float, config: BacktestConfig) -> float:
    return price * (1 - (config.slippage_pct / 100))


def _close_position(
    position: dict[str, float | int],
    exit_time_ms: int,
    exit_price: float,
    equity: float,
    fee_pct: float,
    reason: str,
    symbol: str,
    timeframe: str,
    exit_signal_time_ms: int | None,
) -> tuple[float, BacktestTrade]:
    quantity = float(position["quantity"])
    entry_price = float(position["entry_price"])
    gross_pnl = (exit_price - entry_price) * quantity
    exit_fee = (exit_price * quantity) * (fee_pct / 100)
    entry_fee = float(position["entry_fee"])
    net_pnl = gross_pnl - exit_fee
    new_equity = equity + gross_pnl - exit_fee

    trade = BacktestTrade(
        symbol=symbol,
        timeframe=timeframe,
        entry_time_ms=int(position["entry_time_ms"]),
        exit_time_ms=exit_time_ms,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        gross_pnl=gross_pnl,
        fees=entry_fee + exit_fee,
        net_pnl=net_pnl - entry_fee,
        exit_reason=reason,
        entry_signal_time_ms=(
            int(position["entry_signal_time_ms"]) if "entry_signal_time_ms" in position else None
        ),
        exit_signal_time_ms=exit_signal_time_ms,
    )
    return new_equity, trade
