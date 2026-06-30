from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_bot.data_collector import Candle
from trading_bot.qa import DataQualityGateConfig, evaluate_data_quality_gate, save_data_quality_gate_report


class DataQualityGateTest(unittest.TestCase):
    def test_passes_clean_recent_dataset(self) -> None:
        candles = [
            _candle(900_000, volume=1),
            _candle(1_800_000, volume=2),
            _candle(2_700_000, volume=3),
        ]

        report = evaluate_data_quality_gate(candles, "BTC/USDT", "15m", now_ms=3_600_000)

        self.assertEqual("PASSED", report.status)
        self.assertEqual([], report.blockers)
        self.assertEqual(0, report.stale_candles)

    def test_blocks_gap_duplicate_stale_and_bad_candles(self) -> None:
        candles = [
            _candle(900_000, volume=1),
            _candle(900_000, volume=2),
            _candle(2_700_000, volume=3),
            Candle("BTC/USDT", "15m", 3_600_000, 100, 98, 99, 100, 1),
            Candle("BTC/USDT", "15m", 4_500_000, 0, 101, 99, 100, 1),
        ]

        report = evaluate_data_quality_gate(
            candles,
            "BTC/USDT",
            "15m",
            now_ms=10_800_000,
            config=DataQualityGateConfig(max_stale_candles=2),
        )

        self.assertEqual("BLOCKED", report.status)
        self.assertEqual(1, report.gap_count)
        self.assertEqual(1, report.duplicate_count)
        self.assertEqual(1, report.non_positive_price_count)
        self.assertEqual(1, report.high_low_violation_count)
        self.assertEqual(6, report.stale_candles)
        self.assertTrue(any("gap_count" in blocker for blocker in report.blockers))
        self.assertTrue(any("duplicate_count" in blocker for blocker in report.blockers))
        self.assertTrue(any("non_positive_price_count" in blocker for blocker in report.blockers))
        self.assertTrue(any("high_low_violation_count" in blocker for blocker in report.blockers))
        self.assertTrue(any("stale_candles" in blocker for blocker in report.blockers))

    def test_warns_on_high_zero_volume_rate(self) -> None:
        candles = [
            _candle(900_000, volume=0),
            _candle(1_800_000, volume=0),
            _candle(2_700_000, volume=1),
        ]

        report = evaluate_data_quality_gate(
            candles,
            "BTC/USDT",
            "15m",
            config=DataQualityGateConfig(max_zero_volume_pct=50.0),
        )

        self.assertEqual("WARN", report.status)
        self.assertEqual([], report.blockers)
        self.assertEqual(1, len(report.warnings))

    def test_saves_data_quality_gate_report(self) -> None:
        candles = [_candle(900_000, volume=1)]
        report = evaluate_data_quality_gate(candles, "BTC/USDT", "15m")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_data_quality_gate_report(report, Path(tmpdir))

            self.assertTrue(path.exists())
            self.assertIn('"status": "PASSED"', path.read_text(encoding="utf-8"))


def _candle(open_time_ms: int, volume: float) -> Candle:
    return Candle("BTC/USDT", "15m", open_time_ms, 100, 101, 99, 100, volume)


if __name__ == "__main__":
    unittest.main()
