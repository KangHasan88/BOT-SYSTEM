from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_bot.config import load_config
from trading_bot.research import add_fundamental_event, build_fundamental_report, save_fundamental_report


class FundamentalLaneTest(unittest.TestCase):
    def test_empty_report_is_clear_for_demo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = _write_config(Path(tmpdir))
            config = load_config(config_path)

            report = build_fundamental_report(config)

        self.assertEqual("FUNDAMENTAL_CLEAR", report.status)
        self.assertEqual("LOW", report.top_risk)
        self.assertEqual("green", report.color)
        self.assertEqual(0, report.total_events)

    def test_high_and_block_events_color_risk_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = _write_config(Path(tmpdir))
            config = load_config(config_path)
            add_fundamental_event(
                config,
                symbol="BTC/USDT",
                category="macro",
                risk="high",
                title="US CPI release window",
                note="avoid fresh entries near event",
            )
            add_fundamental_event(
                config,
                symbol="BTC/USDT",
                category="exchange",
                risk="BLOCK",
                title="Exchange maintenance",
            )

            report = build_fundamental_report(config)
            path = save_fundamental_report(report, config.data_root)

            self.assertEqual("FUNDAMENTAL_BLOCK", report.status)
            self.assertEqual("BLOCK", report.top_risk)
            self.assertEqual("red", report.color)
            self.assertEqual(2, report.high_or_block_events)
            self.assertTrue(path.exists())

    def test_rejects_unknown_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = _write_config(Path(tmpdir))
            config = load_config(config_path)

            with self.assertRaises(ValueError):
                add_fundamental_event(config, "BTC/USDT", "news", "extreme", "bad risk")


def _write_config(root: Path) -> Path:
    config_path = root / "bot.toml"
    data_root = root / "data"
    config_path.write_text(
        '[bot]\nmode = "paper"\nlive_enabled = false\napproved_live = false\ntimezone = "Asia/Jakarta"\n'
        '[market]\ntype = "crypto_spot"\nsymbols = ["BTC/USDT", "ETH/USDT"]\ntimeframes = ["15m"]\n'
        '[data]\nroot = "'
        + str(data_root).replace("\\", "\\\\")
        + '"\nprovider = "binance_public"\n'
        '[risk]\nmax_open_positions = 1\ndaily_max_loss_pct = 1.0\nmonthly_max_drawdown_pct = 5.0\n'
        '[sessions]\nentry_windows_wib = ["08:00-11:00"]\nalways_collect_data = true\n',
        encoding="utf-8",
    )
    return config_path


if __name__ == "__main__":
    unittest.main()
