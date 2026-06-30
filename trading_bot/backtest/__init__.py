"""Backtest engine package."""

from trading_bot.backtest.csv_store import BacktestCsvStore
from trading_bot.backtest.engine import run_event_backtest
from trading_bot.backtest.metrics import BacktestMetrics, calculate_backtest_metrics
from trading_bot.backtest.models import BacktestConfig, BacktestResult, BacktestTrade, EquityPoint

__all__ = [
    "BacktestConfig",
    "BacktestCsvStore",
    "BacktestResult",
    "BacktestTrade",
    "EquityPoint",
    "BacktestMetrics",
    "calculate_backtest_metrics",
    "run_event_backtest",
]
