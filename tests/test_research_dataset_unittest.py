from pathlib import Path
import tempfile
import unittest

from trading_bot.data_collector import Candle
from trading_bot.pattern_analyzer import PatternSignal, detect_price_action_patterns
from trading_bot.research import ResearchDatasetCsvStore, build_pattern_outcome_dataset


def candles_with_sweep_down() -> list[Candle]:
    candles: list[Candle] = []
    for index in range(25):
        price = 100.0 + (index * 0.02)
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time_ms=(index + 1) * 900_000,
                open=price,
                high=price + 0.3,
                low=price - 0.3,
                close=price + 0.05,
                volume=100,
            )
        )
    candles.append(
        Candle("BTC/USDT", "15m", 26 * 900_000, 100.5, 100.8, 98.9, 100.6, 250)
    )
    candles.extend(
        [
            Candle("BTC/USDT", "15m", 27 * 900_000, 100.6, 101.4, 100.4, 101.2, 150),
            Candle("BTC/USDT", "15m", 28 * 900_000, 101.2, 102.0, 101.0, 101.8, 150),
            Candle("BTC/USDT", "15m", 29 * 900_000, 101.8, 102.2, 101.6, 102.0, 150),
        ]
    )
    return candles


class ResearchDatasetTest(unittest.TestCase):
    def test_build_pattern_outcome_dataset(self) -> None:
        candles = candles_with_sweep_down()
        patterns = detect_price_action_patterns(candles, lookback=20)
        rows = build_pattern_outcome_dataset(candles, patterns, horizon_candles=3)

        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0].symbol, "BTC/USDT")
        self.assertIn(rows[0].outcome_label, {"GOOD_FOLLOW_THROUGH", "PARTIAL_FOLLOW_THROUGH", "NO_EDGE"})
        self.assertEqual(rows[0].manual_label, "")

    def test_dataset_export(self) -> None:
        candles = candles_with_sweep_down()
        pattern = PatternSignal(
            symbol="BTC/USDT",
            timeframe="15m",
            open_time_ms=26 * 900_000,
            pattern="sweep_down",
            score=0.8,
            reference_price=99.0,
            reason="test",
        )
        rows = build_pattern_outcome_dataset(candles, [pattern], horizon_candles=3)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = ResearchDatasetCsvStore(Path(temp_dir)).write(rows, "BTC/USDT", "15m")
            header = path.read_text(encoding="utf-8").splitlines()[0]
            self.assertTrue(path.exists())

        self.assertIn("manual_label", header)
        self.assertIn("max_favorable_pct", header)

    def test_horizon_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            build_pattern_outcome_dataset([], [], horizon_candles=0)


if __name__ == "__main__":
    unittest.main()
