from pathlib import Path
import json
import tempfile
import unittest

from trading_bot.alerts import AlertOutbox, build_daily_report_alert, build_error_alert, build_stop_alert
from trading_bot.reports.daily_journal import DailyMarketJournal


def journal(review_status: str = "NEUTRAL") -> DailyMarketJournal:
    return DailyMarketJournal(
        symbol="BTC/USDT",
        timeframe="15m",
        report_date_utc="2026-06-29",
        candle_count=96,
        start_time_ms=1,
        end_time_ms=2,
        dominant_regime="mixed",
        regime_counts={"mixed": 96},
        pattern_counts={},
        signal_counts={},
        average_range_pct=0.5,
        average_volume_ratio=1.0,
        paper_trade_count=0,
        paper_net_pnl=0.0,
        backtest_recommendation=None,
        backtest_reason=None,
        review_status=review_status,
        notes=["normal research day"],
    )


class AlertsTest(unittest.TestCase):
    def test_daily_report_alert_warning_for_review_required(self) -> None:
        message = build_daily_report_alert(journal("REVIEW_REQUIRED"))

        self.assertEqual(message.kind, "daily_report")
        self.assertEqual(message.severity, "warning")
        self.assertIn("REVIEW_REQUIRED", message.body)

    def test_stop_alert_is_critical(self) -> None:
        message = build_stop_alert("BTC/USDT", "daily target reached", 1_010.0)

        self.assertEqual(message.kind, "stop")
        self.assertEqual(message.severity, "critical")
        self.assertIn("daily target reached", message.body)

    def test_error_alert(self) -> None:
        message = build_error_alert("collector", "API timeout")

        self.assertEqual(message.kind, "error")
        self.assertEqual(message.severity, "error")
        self.assertIn("collector", message.title)

    def test_outbox_writes_json(self) -> None:
        message = build_stop_alert("BTC/USDT", "profit lock floor hit")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = AlertOutbox(Path(temp_dir)).write(message)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["kind"], "stop")
        self.assertTrue(path.name.endswith("-stop.json"))


if __name__ == "__main__":
    unittest.main()
