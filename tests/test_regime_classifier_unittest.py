from pathlib import Path
import tempfile
import unittest

from trading_bot.data_collector import Candle
from trading_bot.feature_engine import RegimeCsvStore, build_features, classify_regimes


def make_trend(count: int, direction: int = 1, volume: float = 100.0) -> list[Candle]:
    candles: list[Candle] = []
    price = 100.0
    for index in range(count):
        price += direction * 0.5
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time_ms=(index + 1) * 900_000,
                open=price,
                high=price + 0.6,
                low=price - 0.4,
                close=price + (direction * 0.2),
                volume=volume,
            )
        )
    return candles


def make_sideways(count: int) -> list[Candle]:
    candles: list[Candle] = []
    for index in range(count):
        price = 100.0 + (0.05 if index % 2 == 0 else -0.05)
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time_ms=(index + 1) * 900_000,
                open=price,
                high=price + 0.12,
                low=price - 0.12,
                close=price,
                volume=100.0,
            )
        )
    return candles


class RegimeClassifierTest(unittest.TestCase):
    def test_trending_up(self) -> None:
        rows = classify_regimes(build_features(make_trend(60, direction=1)))

        self.assertEqual(rows[-1].regime, "trending_up")

    def test_trending_down(self) -> None:
        rows = classify_regimes(build_features(make_trend(60, direction=-1)))

        self.assertEqual(rows[-1].regime, "trending_down")

    def test_sideways(self) -> None:
        rows = classify_regimes(build_features(make_sideways(60)))

        self.assertEqual(rows[-1].regime, "sideways")

    def test_volatile_overrides_trend(self) -> None:
        candles = make_trend(60, direction=1)
        candles[-1] = Candle("BTC/USDT", "15m", 60 * 900_000, 120, 130, 110, 121, 100)
        rows = classify_regimes(build_features(candles))

        self.assertEqual(rows[-1].regime, "volatile")

    def test_low_liquidity_overrides_other_regime(self) -> None:
        candles = make_trend(60, direction=1)
        candles[-1] = Candle("BTC/USDT", "15m", 60 * 900_000, 130, 130.5, 129.5, 130.2, 1)
        rows = classify_regimes(build_features(candles))

        self.assertEqual(rows[-1].regime, "low_liquidity")

    def test_regime_csv_export(self) -> None:
        rows = classify_regimes(build_features(make_trend(60, direction=1)))

        with tempfile.TemporaryDirectory() as temp_dir:
            path = RegimeCsvStore(Path(temp_dir)).write(rows, "BTC/USDT", "15m")

            self.assertTrue(path.exists())
            self.assertIn("regime", path.read_text(encoding="utf-8").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
