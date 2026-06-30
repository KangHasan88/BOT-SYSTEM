from pathlib import Path
import tempfile
import unittest

from trading_bot.data_collector import Candle, CandleCsvStore
from trading_bot.feature_engine import FeatureConfig, FeatureCsvStore, build_features, ema, rsi, sma


def make_candles(count: int) -> list[Candle]:
    candles: list[Candle] = []
    for index in range(count):
        open_price = 100 + index
        close_price = open_price + (1 if index % 2 == 0 else -0.5)
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time_ms=(index + 1) * 900_000,
                open=open_price,
                high=open_price + 2,
                low=open_price - 1,
                close=close_price,
                volume=10 + index,
            )
        )
    return candles


class FeatureEngineTest(unittest.TestCase):
    def test_ema_and_sma_warmup(self) -> None:
        self.assertEqual(ema([1, 2, 3, 4], 3), [None, None, 2.0, 3.0])
        self.assertEqual(sma([1, 2, 3, 4], 2), [None, 1.5, 2.5, 3.5])

    def test_rsi_bounds(self) -> None:
        values = [100, 101, 102, 101, 103, 104, 103, 105, 106, 107, 106, 108, 109, 110, 111]
        rsi_values = rsi(values, 14)

        self.assertIsNone(rsi_values[13])
        self.assertIsNotNone(rsi_values[14])
        self.assertGreaterEqual(rsi_values[14], 0)
        self.assertLessEqual(rsi_values[14], 100)

    def test_features_include_wick_and_volume_spike(self) -> None:
        rows = build_features(make_candles(30), FeatureConfig(volume_sma_period=3))

        self.assertEqual(len(rows), 30)
        self.assertGreater(rows[-1].range_pct, 0)
        self.assertGreaterEqual(rows[-1].upper_wick_pct, 0)
        self.assertGreaterEqual(rows[-1].lower_wick_pct, 0)
        self.assertIsNotNone(rows[-1].volume_spike_ratio)

    def test_no_lookahead_for_previous_rows(self) -> None:
        base_rows = build_features(make_candles(30))
        extended_rows = build_features(make_candles(31))

        self.assertEqual(base_rows[20], extended_rows[20])
        self.assertEqual(base_rows[-1], extended_rows[29])

    def test_feature_csv_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            candles = make_candles(30)
            CandleCsvStore(Path(temp_dir)).upsert_many(candles)
            rows = build_features(CandleCsvStore(Path(temp_dir)).load("BTC/USDT", "15m"))
            path = FeatureCsvStore(Path(temp_dir)).write(rows)

            self.assertIsNotNone(path)
            assert path is not None
            self.assertTrue(path.exists())
            self.assertIn("ema_fast", path.read_text(encoding="utf-8").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
