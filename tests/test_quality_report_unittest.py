from pathlib import Path
import json
import tempfile
import unittest

from trading_bot.data_collector.models import QualityReport
from trading_bot.reports.quality import save_quality_report


class QualityReportExportTest(unittest.TestCase):
    def test_save_quality_report(self) -> None:
        report = QualityReport(
            symbol="BTC/USDT",
            timeframe="15m",
            candle_count=10,
            first_open_time_ms=900_000,
            last_open_time_ms=9_000_000,
            gap_count=0,
            duplicate_count=0,
            zero_volume_count=0,
            non_positive_price_count=0,
            dataset_id="abc123",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = save_quality_report(report, Path(temp_dir))
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["symbol"], "BTC/USDT")
        self.assertEqual(payload["dataset_id"], "abc123")


if __name__ == "__main__":
    unittest.main()
