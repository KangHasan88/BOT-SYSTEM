from __future__ import annotations

from dataclasses import dataclass

from trading_bot.backtest import BacktestConfig, BacktestMetrics, calculate_backtest_metrics, run_event_backtest
from trading_bot.data_collector.market_context import SymbolMetadata
from trading_bot.data_collector.models import Candle


@dataclass(frozen=True)
class WalkForwardConfig:
    train_candles: int = 240
    test_candles: int = 120
    step_candles: int = 120
    min_test_trades: int = 5
    initial_equity: float = 1_000.0


@dataclass(frozen=True)
class WalkForwardFoldResult:
    fold_number: int
    train_start_ms: int
    train_end_ms: int
    test_start_ms: int
    test_end_ms: int
    train_metrics: BacktestMetrics
    test_metrics: BacktestMetrics


@dataclass(frozen=True)
class WalkForwardReport:
    symbol: str
    timeframe: str
    fold_count: int
    total_test_trades: int
    average_test_return_pct: float
    average_test_drawdown_pct: float
    pass_count: int
    fail_count: int
    recommendation: str
    reason: str
    folds: list[WalkForwardFoldResult]


def run_walk_forward_validation(
    candles: list[Candle],
    metadata: SymbolMetadata,
    config: WalkForwardConfig | None = None,
) -> WalkForwardReport:
    if config is None:
        config = WalkForwardConfig()
    _validate_config(config)

    ordered = sorted(candles, key=lambda candle: candle.open_time_ms)
    if not ordered:
        return WalkForwardReport(metadata.symbol, "", 0, 0, 0.0, 0.0, 0, 0, "NOT_ENOUGH_DATA", "no candles", [])

    folds: list[WalkForwardFoldResult] = []
    start = 0
    fold_number = 1
    while start + config.train_candles + config.test_candles <= len(ordered):
        train = ordered[start : start + config.train_candles]
        test = ordered[start + config.train_candles : start + config.train_candles + config.test_candles]
        train_result = run_event_backtest(
            train,
            metadata=metadata,
            config=BacktestConfig(initial_equity=config.initial_equity),
        )
        test_result = run_event_backtest(
            test,
            metadata=metadata,
            config=BacktestConfig(initial_equity=config.initial_equity),
        )
        folds.append(
            WalkForwardFoldResult(
                fold_number=fold_number,
                train_start_ms=train[0].open_time_ms,
                train_end_ms=train[-1].open_time_ms,
                test_start_ms=test[0].open_time_ms,
                test_end_ms=test[-1].open_time_ms,
                train_metrics=calculate_backtest_metrics(train_result),
                test_metrics=calculate_backtest_metrics(test_result),
            )
        )
        fold_number += 1
        start += config.step_candles

    return _build_report(ordered[0].symbol, ordered[0].timeframe, folds, config)


def _build_report(
    symbol: str,
    timeframe: str,
    folds: list[WalkForwardFoldResult],
    config: WalkForwardConfig,
) -> WalkForwardReport:
    if not folds:
        return WalkForwardReport(
            symbol=symbol,
            timeframe=timeframe,
            fold_count=0,
            total_test_trades=0,
            average_test_return_pct=0.0,
            average_test_drawdown_pct=0.0,
            pass_count=0,
            fail_count=0,
            recommendation="NOT_ENOUGH_DATA",
            reason="not enough candles to build one train/test fold",
            folds=[],
        )

    total_test_trades = sum(fold.test_metrics.trade_count for fold in folds)
    average_return = sum(fold.test_metrics.total_return_pct for fold in folds) / len(folds)
    average_drawdown = sum(fold.test_metrics.max_drawdown_pct for fold in folds) / len(folds)
    pass_count = sum(1 for fold in folds if _fold_passes(fold, config))
    fail_count = len(folds) - pass_count
    recommendation, reason = _recommend(
        folds=folds,
        total_test_trades=total_test_trades,
        pass_count=pass_count,
        average_return=average_return,
        average_drawdown=average_drawdown,
        config=config,
    )

    return WalkForwardReport(
        symbol=symbol,
        timeframe=timeframe,
        fold_count=len(folds),
        total_test_trades=total_test_trades,
        average_test_return_pct=average_return,
        average_test_drawdown_pct=average_drawdown,
        pass_count=pass_count,
        fail_count=fail_count,
        recommendation=recommendation,
        reason=reason,
        folds=folds,
    )


def _fold_passes(fold: WalkForwardFoldResult, config: WalkForwardConfig) -> bool:
    metrics = fold.test_metrics
    return (
        metrics.trade_count >= config.min_test_trades
        and metrics.total_return_pct > 0
        and metrics.expectancy > 0
        and metrics.max_drawdown_pct <= 8.0
        and metrics.longest_losing_streak <= 6
    )


def _recommend(
    folds: list[WalkForwardFoldResult],
    total_test_trades: int,
    pass_count: int,
    average_return: float,
    average_drawdown: float,
    config: WalkForwardConfig,
) -> tuple[str, str]:
    if len(folds) < 2:
        return "NOT_ENOUGH_DATA", "walk-forward needs at least 2 folds"
    if total_test_trades < config.min_test_trades * len(folds):
        return "NOT_ENOUGH_DATA", "test trade sample too small"
    if pass_count < len(folds):
        return "REJECT", "one or more out-of-sample folds failed"
    if average_return <= 0:
        return "REJECT", "average out-of-sample return is not positive"
    if average_drawdown > 8.0:
        return "REJECT", "average out-of-sample drawdown above threshold"
    return "PAPER_CANDIDATE", "all out-of-sample folds passed conservative gate"


def _validate_config(config: WalkForwardConfig) -> None:
    if config.train_candles < 1:
        raise ValueError("train_candles must be >= 1")
    if config.test_candles < 1:
        raise ValueError("test_candles must be >= 1")
    if config.step_candles < 1:
        raise ValueError("step_candles must be >= 1")
    if config.min_test_trades < 0:
        raise ValueError("min_test_trades must be >= 0")
