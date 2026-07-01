from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.config import load_config
from trading_bot.research import build_learning_dashboard_report, save_learning_dashboard_report


class LearningDashboardTest(unittest.TestCase):
    def test_learning_dashboard_needs_data_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")
            config = load_config(config_path)

            report = build_learning_dashboard_report(config)

        self.assertEqual("LEARNING_DASHBOARD_NEEDS_DATA", report.status)
        self.assertIn("never trigger live", report.guardrail)

    def test_learning_dashboard_combines_memory_learning_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            config = load_config(config_path)
            _write_json(
                data_root / "reports" / "learning" / "database_snapshot.json",
                {
                    "rows": [
                        {
                            "symbol": "BTC/USDT",
                            "timeframe": "15m",
                            "observation": "WATCH_VOLUME_SPIKE",
                            "latest_volume_ratio": 2.1,
                            "pattern_counts": {"sweep_down": 2},
                        }
                    ]
                },
            )
            _write_json(
                data_root / "reports" / "learning" / "pattern_memory.json",
                {
                    "rows": [
                        {
                            "symbol": "BTC/USDT",
                            "timeframe": "15m",
                            "observation": "WATCH_VOLUME_SPIKE",
                            "outcome_grade": "NEEDS_MORE_TRADES",
                            "trade_count": 3,
                            "win_rate_pct": 66.67,
                            "total_net_pnl": 1.2,
                            "next_action": "Lanjut paper campaign",
                        }
                    ]
                },
            )
            _write_json(data_root / "readiness" / "live_evidence.json", {"completion_pct": 50.0})
            _write_json(data_root / "qa" / "paper_campaign" / "report.json", {"completion_pct": 40.0})

            report = build_learning_dashboard_report(config)
            path = save_learning_dashboard_report(report, config.data_root)
            path_exists = path.exists()

        self.assertTrue(path_exists)
        self.assertEqual("LEARNING_DASHBOARD_ACTIVE", report.status)
        self.assertEqual(1, report.trend_count)
        self.assertEqual(1, report.volume_spike_count)
        self.assertGreater(report.average_evidence_score, 0)
        self.assertEqual("BUTUH PAPER", report.trends[0].status)


def _write_config(path: Path, data_root: Path) -> None:
    path.write_text(
        '[bot]\nmode = "research"\nlive_enabled = false\napproved_live = false\ntimezone = "Asia/Jakarta"\n'
        '[market]\ntype = "crypto_spot"\nsymbols = ["BTC/USDT"]\ntimeframes = ["15m"]\n'
        '[data]\nroot = "'
        + str(data_root).replace("\\", "\\\\")
        + '"\nprovider = "binance_public"\n'
        '[risk]\nmax_open_positions = 1\n'
        '[sessions]\nentry_windows_wib = ["08:00-11:00"]\nalways_collect_data = true\n',
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
