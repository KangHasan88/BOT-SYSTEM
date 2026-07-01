from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.config import load_config
from trading_bot.qa import EvidenceCampaignConfig, run_evidence_campaign, save_evidence_campaign_report


class EvidenceCampaignTest(unittest.TestCase):
    def test_campaign_seeds_demo_and_writes_readiness_report(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")
            config = load_config(config_path)

            report = run_evidence_campaign(
                config,
                EvidenceCampaignConfig(
                    seed_demo_if_needed=True,
                    candles_per_pair=90,
                    min_candles=80,
                    min_paper_trades=1,
                    paper_min_days=1,
                    paper_min_trades=1,
                    walk_forward_train_candles=30,
                    walk_forward_test_candles=20,
                    walk_forward_step_candles=20,
                    walk_forward_min_test_trades=0,
                ),
            )
            path = save_evidence_campaign_report(report, config.data_root)
            payload = json.loads(path.read_text(encoding="utf-8"))

            self.assertTrue(path.exists())
            self.assertEqual(report.status, payload["status"])

        self.assertTrue(report.seeded_demo_data)
        self.assertEqual(1, report.pairs_checked)
        self.assertIn(report.status, {"EVIDENCE_READY", "EVIDENCE_INCOMPLETE"})
        self.assertTrue(any(step.name == "data_quality_gate" for step in report.steps))
        self.assertTrue(any(step.name == "live_evidence" for step in report.steps))


def _write_config(path: Path, data_root: Path) -> None:
    path.write_text(
        '[bot]\nmode = "research"\nlive_enabled = false\napproved_live = false\ntimezone = "Asia/Jakarta"\n'
        '[market]\ntype = "crypto_spot"\nsymbols = ["BTC/USDT"]\ntimeframes = ["1h"]\n'
        '[data]\nroot = "'
        + str(data_root).replace("\\", "\\\\")
        + '"\nprovider = "binance_public"\n'
        '[risk]\nmax_open_positions = 1\n'
        '[sessions]\nentry_windows_wib = ["08:00-11:00", "19:00-23:30"]\nalways_collect_data = true\n',
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
