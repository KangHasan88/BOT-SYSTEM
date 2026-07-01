from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_bot.config import load_config
from trading_bot.demo import build_local_demo_report, save_local_demo_report, seed_demo_data_pack
from trading_bot.storage import load_database_status


class DemoDataPackTest(unittest.TestCase):
    def test_seed_demo_data_pack_creates_usable_local_outputs(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")
            config = load_config(config_path)

            result = seed_demo_data_pack(config, candles_per_pair=90)
            db_status = load_database_status(config.data_root)

            self.assertGreater(result.candle_rows, 0)
            self.assertGreater(result.cycle_candles_seen, 0)
            self.assertGreater(result.database_rows, 0)
            self.assertTrue(Path(result.learning_report_path).exists())
            self.assertTrue(Path(result.dashboard_path).exists())
            self.assertTrue(db_status.exists)
            self.assertGreater(db_status.total_rows, 0)

    def test_seed_demo_data_pack_requires_enough_candles(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")
            config = load_config(config_path)

            with self.assertRaises(ValueError):
                seed_demo_data_pack(config, candles_per_pair=20)

    def test_local_demo_report_can_seed_and_verify_safe_path(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")
            config = load_config(config_path)

            report = build_local_demo_report(config, seed_demo_if_needed=True, candles_per_pair=180)
            path = save_local_demo_report(report, config.data_root)
            path_exists = path.exists()

        self.assertTrue(path_exists)
        self.assertTrue(report.seeded_demo_data)
        self.assertTrue(report.live_locked)
        self.assertGreater(report.candle_rows, 0)
        self.assertGreater(report.paper_trades, 0)
        self.assertEqual("READY_FOR_LOCAL_DEMO", report.status)
        self.assertTrue(any(check.name == "pnl_monitor" for check in report.checks))


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


if __name__ == "__main__":
    unittest.main()
