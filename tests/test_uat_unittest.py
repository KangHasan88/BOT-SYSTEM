from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.config import load_config
from trading_bot.qa import build_uat_report, save_uat_report


class UatReportTest(unittest.TestCase):
    def test_uat_report_tracks_demo_readiness_and_live_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = load_config(_write_config(root))
            _write_demo_files(Path(config.data_root))

            report = build_uat_report(config)
            path = save_uat_report(report, config.data_root)

            self.assertEqual("UAT_READY_FOR_DEMO", report.status)
            self.assertEqual(0, report.bug_count)
            self.assertGreaterEqual(report.completion_pct, 85)
            self.assertTrue(path.exists())
            self.assertIn("demo/paper ready only", report.guardrail)

    def test_uat_report_exposes_open_bugs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = load_config(_write_config(root))
            _write_demo_files(Path(config.data_root))
            bug_path = Path(config.data_root) / "qa" / "uat" / "bugs.json"
            bug_path.parent.mkdir(parents=True, exist_ok=True)
            bug_path.write_text(json.dumps({"bugs": ["button label unclear"]}), encoding="utf-8")

            report = build_uat_report(config)

        self.assertEqual("UAT_HAS_BUGS", report.status)
        self.assertEqual(1, report.bug_count)


def _write_config(root: Path) -> Path:
    config_path = root / "bot.toml"
    data_root = root / "data"
    config_path.write_text(
        '[bot]\nmode = "paper"\nlive_enabled = false\napproved_live = false\ntimezone = "Asia/Jakarta"\n'
        '[market]\ntype = "crypto_spot"\nsymbols = ["BTC/USDT"]\ntimeframes = ["15m"]\n'
        '[data]\nroot = "'
        + str(data_root).replace("\\", "\\\\")
        + '"\nprovider = "binance_public"\n'
        '[risk]\nmax_open_positions = 1\ndaily_max_loss_pct = 1.0\nmonthly_max_drawdown_pct = 5.0\n'
        '[sessions]\nentry_windows_wib = ["08:00-11:00"]\nalways_collect_data = true\n',
        encoding="utf-8",
    )
    return config_path


def _write_demo_files(root: Path) -> None:
    (root / "demo").mkdir(parents=True, exist_ok=True)
    (root / "demo" / "local_demo.json").write_text("{}", encoding="utf-8")
    paper = root / "paper" / "BTC_USDT" / "15m"
    paper.mkdir(parents=True, exist_ok=True)
    (paper / "trades.csv").write_text("symbol,timeframe,net_pnl\nBTC/USDT,15m,1.0\n", encoding="utf-8")
    (root / "reports" / "fundamental").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "fundamental" / "report.json").write_text("{}", encoding="utf-8")
    (root / "reports" / "learning").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "learning" / "experiment_scoreboard.json").write_text("{}", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
