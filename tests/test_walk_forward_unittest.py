from pathlib import Path
import json
import tempfile
import unittest

from trading_bot.data_collector import Candle
from trading_bot.data_collector.market_context import SymbolMetadata
from trading_bot.reports.walk_forward import save_walk_forward_report
from trading_bot.validation import WalkForwardConfig, run_walk_forward_validation


def metadata() -> SymbolMetadata:
    return SymbolMetadata("BTC/USDT", "BTC", "USDT", 1.0, 8, 8, 0.10, 0.10)


def uptrend_candles(count: int = 160) -> list[Candle]:
    candles: list[Candle] = []
    price = 100.0
    for index in range(count):
        price += 0.06
        close_offset = 0.10
        if index % 6 == 0:
            price -= 0.12
            close_offset = -0.08
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time_ms=(index + 1) * 900_000,
                open=price,
                high=price + 0.60,
                low=price - 0.35,
                close=price + close_offset,
                volume=100.0,
            )
        )
    return candles


class WalkForwardTest(unittest.TestCase):
    def test_empty_validation(self) -> None:
        report = run_walk_forward_validation([], metadata())

        self.assertEqual(report.recommendation, "NOT_ENOUGH_DATA")
        self.assertEqual(report.fold_count, 0)

    def test_not_enough_candles_for_fold(self) -> None:
        report = run_walk_forward_validation(
            uptrend_candles(20),
            metadata(),
            WalkForwardConfig(train_candles=20, test_candles=20, step_candles=10),
        )

        self.assertEqual(report.recommendation, "NOT_ENOUGH_DATA")
        self.assertEqual(report.reason, "not enough candles to build one train/test fold")

    def test_builds_multiple_folds(self) -> None:
        report = run_walk_forward_validation(
            uptrend_candles(140),
            metadata(),
            WalkForwardConfig(train_candles=40, test_candles=30, step_candles=30, min_test_trades=0),
        )

        self.assertGreaterEqual(report.fold_count, 2)
        self.assertEqual(len(report.folds), report.fold_count)
        self.assertIn(report.recommendation, {"PAPER_CANDIDATE", "REJECT", "NOT_ENOUGH_DATA"})

    def test_save_walk_forward_report(self) -> None:
        report = run_walk_forward_validation(
            uptrend_candles(140),
            metadata(),
            WalkForwardConfig(train_candles=40, test_candles=30, step_candles=30, min_test_trades=0),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = save_walk_forward_report(report, Path(temp_dir), "BTC/USDT", "15m")
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(path.name.endswith(".json"))
        self.assertEqual(payload["symbol"], "BTC/USDT")
        self.assertIn("folds", payload)

    def test_invalid_config(self) -> None:
        with self.assertRaises(ValueError):
            run_walk_forward_validation([], metadata(), WalkForwardConfig(train_candles=0))


if __name__ == "__main__":
    unittest.main()
