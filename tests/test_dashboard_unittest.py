from pathlib import Path
import json
import tempfile
import unittest

from trading_bot.dashboard import DashboardData, build_review_dashboard, save_review_dashboard


class DashboardTest(unittest.TestCase):
    def test_build_dashboard_with_empty_data(self) -> None:
        html = build_review_dashboard(DashboardData([], [], [], []))

        self.assertIn("Trading Bot Review Dashboard", html)
        self.assertIn("No daily reports yet.", html)

    def test_build_dashboard_escapes_report_notes(self) -> None:
        html = build_review_dashboard(
            DashboardData(
                daily_reports=[
                    {
                        "report_date_utc": "2026-06-29",
                        "symbol": "BTC/USDT",
                        "timeframe": "15m",
                        "dominant_regime": "mixed",
                        "review_status": "REVIEW_REQUIRED",
                        "notes": ["<script>alert(1)</script>"],
                    }
                ],
                backtest_metrics=[],
                paper_accounts=[],
                paper_trades=[],
            )
        )

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_save_dashboard_loads_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_dir = root / "reports" / "daily" / "BTC_USDT" / "15m"
            report_dir.mkdir(parents=True)
            (report_dir / "2026-06-29.json").write_text(
                json.dumps(
                    {
                        "report_date_utc": "2026-06-29",
                        "symbol": "BTC/USDT",
                        "timeframe": "15m",
                        "dominant_regime": "trending_up",
                        "review_status": "NEUTRAL",
                        "notes": ["normal research day"],
                    }
                ),
                encoding="utf-8",
            )

            path = save_review_dashboard(root)
            html = path.read_text(encoding="utf-8")

        self.assertTrue(path.name.endswith(".html"))
        self.assertIn("BTC/USDT", html)
        self.assertIn("trending_up", html)


if __name__ == "__main__":
    unittest.main()
