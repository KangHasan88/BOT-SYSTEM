from pathlib import Path
import tempfile
import unittest

from trading_bot.backtest import BacktestConfig, BacktestCsvStore, run_event_backtest
from trading_bot.data_collector import Candle
from trading_bot.data_collector.market_context import SymbolMetadata


def metadata() -> SymbolMetadata:
    return SymbolMetadata("BTC/USDT", "BTC", "USDT", 1.0, 8, 8, 0.10, 0.10)


def uptrend_candles(count: int = 80) -> list[Candle]:
    candles: list[Candle] = []
    price = 100.0
    for index in range(count):
        price += 0.05
        close_offset = 0.08
        if index % 6 == 0:
            price -= 0.10
            close_offset = -0.08
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time_ms=(index + 1) * 900_000,
                open=price,
                high=price + 0.55,
                low=price - 0.35,
                close=price + close_offset,
                volume=100.0,
            )
        )
    return candles


class BacktestEngineTest(unittest.TestCase):
    def test_empty_backtest(self) -> None:
        result = run_event_backtest([], metadata())

        self.assertEqual(result.final_equity, 1_000.0)
        self.assertEqual(result.trades, [])

    def test_uptrend_generates_trade_and_equity_curve(self) -> None:
        result = run_event_backtest(uptrend_candles(), metadata())

        self.assertGreaterEqual(len(result.equity_curve), len(uptrend_candles()))
        self.assertGreaterEqual(len(result.trades), 1)

    def test_stop_loss_can_close_trade(self) -> None:
        candles = uptrend_candles(60)
        candles.append(Candle("BTC/USDT", "15m", 61 * 900_000, 130, 131, 90, 101, 100))
        result = run_event_backtest(candles, metadata())

        self.assertIn("STOP_LOSS", {trade.exit_reason for trade in result.trades})

    def test_fees_reduce_equity(self) -> None:
        no_fee = run_event_backtest(
            uptrend_candles(),
            metadata(),
            BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
        )
        with_fee = run_event_backtest(
            uptrend_candles(),
            metadata(),
            BacktestConfig(fee_pct=0.10, slippage_pct=0.02),
        )

        self.assertLess(with_fee.final_equity, no_fee.final_equity)

    def test_entries_execute_after_signal_candle(self) -> None:
        result = run_event_backtest(uptrend_candles(), metadata())

        self.assertTrue(result.trades)
        for trade in result.trades:
            if trade.entry_signal_time_ms is not None:
                self.assertGreater(trade.entry_time_ms, trade.entry_signal_time_ms)

    def test_backtest_csv_export(self) -> None:
        result = run_event_backtest(uptrend_candles(), metadata())
        with tempfile.TemporaryDirectory() as temp_dir:
            trades_path, equity_path = BacktestCsvStore(Path(temp_dir)).write(result)

            self.assertTrue(trades_path.exists())
            self.assertTrue(equity_path.exists())
            self.assertIn("net_pnl", trades_path.read_text(encoding="utf-8").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
