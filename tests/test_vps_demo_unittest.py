from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.config import load_config
from trading_bot.demo import build_vps_demo_report, save_vps_demo_report


class VpsDemoTest(unittest.TestCase):
    def test_vps_demo_report_accepts_private_paper_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_runtime_config(config_path, data_root)
            _write_json(data_root / "demo" / "local_demo.json", {"status": "READY_FOR_LOCAL_DEMO"})
            _write_json(data_root / "qa" / "paper_campaign" / "report.json", {"status": "PAPER_CAMPAIGN_COLLECTING"})
            config = load_config(config_path)

            report = build_vps_demo_report(config)
            path = save_vps_demo_report(report, config.data_root)
            path_exists = path.exists()

        self.assertTrue(path_exists)
        self.assertEqual("READY_FOR_PRIVATE_VPS_DEMO", report.status)
        self.assertTrue(report.live_locked)
        self.assertEqual("http://127.0.0.1:18000/", report.tunnel_url)
        self.assertTrue(all(check.status == "PASS" for check in report.checks))

    def test_vps_demo_report_blocks_live_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_runtime_config(config_path, root / "data", mode="live", live_enabled=True, approved_live=True)
            config = load_config(config_path)

            report = build_vps_demo_report(config)

        self.assertEqual("VPS_DEMO_PREP", report.status)
        failed = {check.name for check in report.checks if check.status == "FAIL"}
        self.assertIn("live_lock", failed)


def _write_runtime_config(
    path: Path,
    data_root: Path,
    mode: str = "paper",
    live_enabled: bool = False,
    approved_live: bool = False,
) -> None:
    path.write_text(
        '[bot]\nmode = "'
        + mode
        + '"\nlive_enabled = '
        + str(live_enabled).lower()
        + "\napproved_live = "
        + str(approved_live).lower()
        + '\ntimezone = "Asia/Jakarta"\n'
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
