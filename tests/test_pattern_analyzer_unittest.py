from pathlib import Path
import tempfile
import unittest

from trading_bot.data_collector import Candle
from trading_bot.pattern_analyzer import (
    PatternCsvStore,
    detect_price_action_patterns,
    detect_swing_points,
)


def base_history(count: int = 20) -> list[Candle]:
    candles: list[Candle] = []
    for index in range(count):
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time_ms=(index + 1) * 900_000,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=10.0,
            )
        )
    return candles


class PatternAnalyzerTest(unittest.TestCase):
    def test_detect_swing_points(self) -> None:
        candles = [
            Candle("BTC/USDT", "15m", 1, 10, 11, 9, 10, 1),
            Candle("BTC/USDT", "15m", 2, 10, 12, 8, 10, 1),
            Candle("BTC/USDT", "15m", 3, 10, 15, 7, 10, 1),
            Candle("BTC/USDT", "15m", 4, 10, 12, 8, 10, 1),
            Candle("BTC/USDT", "15m", 5, 10, 11, 9, 10, 1),
        ]

        swings = detect_swing_points(candles, left=2, right=2)

        self.assertEqual({swing.kind for swing in swings}, {"swing_high", "swing_low"})

    def test_sweep_down_and_false_breakout_down(self) -> None:
        candles = base_history()
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time_ms=21 * 900_000,
                open=99.5,
                high=101.0,
                low=98.0,
                close=100.5,
                volume=30.0,
            )
        )

        signals = detect_price_action_patterns(candles, lookback=20)
        patterns = {signal.pattern for signal in signals}

        self.assertIn("sweep_down", patterns)
        self.assertIn("false_breakout_down", patterns)

    def test_sweep_up_and_false_breakout_up(self) -> None:
        candles = base_history()
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time_ms=21 * 900_000,
                open=100.5,
                high=102.0,
                low=99.0,
                close=99.5,
                volume=30.0,
            )
        )

        signals = detect_price_action_patterns(candles, lookback=20)
        patterns = {signal.pattern for signal in signals}

        self.assertIn("sweep_up", patterns)
        self.assertIn("false_breakout_up", patterns)

    def test_absorption_candidate(self) -> None:
        candles = base_history()
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time_ms=21 * 900_000,
                open=100.0,
                high=104.0,
                low=96.0,
                close=100.2,
                volume=40.0,
            )
        )

        signals = detect_price_action_patterns(candles, lookback=20)

        self.assertIn("absorption_candidate", {signal.pattern for signal in signals})

    def test_pattern_csv_export(self) -> None:
        candles = base_history()
        candles.append(Candle("BTC/USDT", "15m", 21 * 900_000, 99.5, 101, 98, 100.5, 30))
        signals = detect_price_action_patterns(candles, lookback=20)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = PatternCsvStore(Path(temp_dir)).write(signals, "BTC/USDT", "15m")

            self.assertTrue(path.exists())
            self.assertIn("pattern", path.read_text(encoding="utf-8").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
