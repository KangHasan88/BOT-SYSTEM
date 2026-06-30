from pathlib import Path
import json
import tempfile
import unittest

from trading_bot.backtest import BacktestResult, BacktestTrade, EquityPoint, calculate_backtest_metrics
from trading_bot.reports.backtest import save_backtest_metrics_report


def trade(net_pnl: float, entry: float = 100.0, exit: float | None = None) -> BacktestTrade:
    exit_price = exit if exit is not None else entry + net_pnl
    return BacktestTrade(
        symbol="BTC/USDT",
        timeframe="15m",
        entry_time_ms=1,
        exit_time_ms=2,
        entry_price=entry,
        exit_price=exit_price,
        quantity=1.0,
        gross_pnl=net_pnl,
        fees=0.0,
        net_pnl=net_pnl,
        exit_reason="TEST",
        entry_signal_time_ms=0,
    )


def result_with(trades: list[BacktestTrade], equity_values: list[float]) -> BacktestResult:
    return BacktestResult(
        symbol="BTC/USDT",
        timeframe="15m",
        initial_equity=1_000.0,
        final_equity=equity_values[-1],
        trades=trades,
        equity_curve=[
            EquityPoint(index + 1, equity)
            for index, equity in enumerate(equity_values)
        ],
    )


class BacktestMetricsTest(unittest.TestCase):
    def test_no_trades_not_enough_data(self) -> None:
        metrics = calculate_backtest_metrics(result_with([], [1_000.0]))

        self.assertEqual(metrics.trade_count, 0)
        self.assertEqual(metrics.recommendation, "NOT_ENOUGH_DATA")

    def test_drawdown_and_losing_streak(self) -> None:
        metrics = calculate_backtest_metrics(
            result_with(
                [trade(-1), trade(-2), trade(3)],
                [1_000.0, 1_010.0, 990.0, 1_005.0],
            )
        )

        self.assertAlmostEqual(metrics.max_drawdown_pct, 1.9801980198019802)
        self.assertEqual(metrics.longest_losing_streak, 2)

    def test_reject_negative_expectancy(self) -> None:
        trades = [trade(-2) for _ in range(31)]
        metrics = calculate_backtest_metrics(result_with(trades, [1_000.0, 938.0]))

        self.assertEqual(metrics.recommendation, "REJECT")

    def test_paper_candidate(self) -> None:
        trades = [trade(3), trade(3), trade(3), trade(-1)] * 8
        metrics = calculate_backtest_metrics(result_with(trades, [1_000.0, 1_064.0]))

        self.assertEqual(metrics.trade_count, 32)
        self.assertGreater(metrics.profit_factor, 1.3)
        self.assertEqual(metrics.recommendation, "PAPER_CANDIDATE")

    def test_save_metrics_report(self) -> None:
        metrics = calculate_backtest_metrics(result_with([], [1_000.0]))
        with tempfile.TemporaryDirectory() as temp_dir:
            path = save_backtest_metrics_report(metrics, Path(temp_dir), "BTC/USDT", "15m")
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["recommendation"], "NOT_ENOUGH_DATA")
        self.assertIn("fee_pct", payload)
        self.assertIn("slippage_pct", payload)
        self.assertIn("no_lookahead_passed", payload)

    def test_no_lookahead_failure_rejects_large_sample(self) -> None:
        trades = [
            BacktestTrade(
                symbol="BTC/USDT",
                timeframe="15m",
                entry_time_ms=1,
                exit_time_ms=2,
                entry_price=100.0,
                exit_price=101.0,
                quantity=1.0,
                gross_pnl=1.0,
                fees=0.0,
                net_pnl=1.0,
                exit_reason="TEST",
                entry_signal_time_ms=1,
            )
            for _ in range(31)
        ]
        metrics = calculate_backtest_metrics(result_with(trades, [1_000.0, 1_031.0]))

        self.assertFalse(metrics.no_lookahead_passed)
        self.assertEqual(metrics.recommendation, "REJECT")

    def test_positive_gross_negative_net_is_rejected(self) -> None:
        trades = [
            BacktestTrade(
                symbol="BTC/USDT",
                timeframe="15m",
                entry_time_ms=index + 2,
                exit_time_ms=index + 3,
                entry_price=100.0,
                exit_price=101.0,
                quantity=1.0,
                gross_pnl=1.0,
                fees=2.0,
                net_pnl=-1.0,
                exit_reason="TEST",
                entry_signal_time_ms=index + 1,
            )
            for index in range(31)
        ]
        metrics = calculate_backtest_metrics(result_with(trades, [1_000.0, 969.0]))

        self.assertGreater(metrics.gross_return_pct, 0)
        self.assertLess(metrics.total_return_pct, 0)
        self.assertEqual(metrics.recommendation, "REJECT")


if __name__ == "__main__":
    unittest.main()
