from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_bot.config import load_config
from trading_bot.research import add_strategy_experiment, build_experiment_scoreboard, save_experiment_scoreboard


class ExperimentRegistryTest(unittest.TestCase):
    def test_empty_scoreboard_is_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_config(_write_config(Path(tmpdir)))

            report = build_experiment_scoreboard(config)

        self.assertEqual("EXPERIMENT_SCOREBOARD_EMPTY", report.status)
        self.assertEqual(0, report.experiment_count)
        self.assertIn("review-only", report.guardrail)

    def test_scoreboard_ranks_experiments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_config(_write_config(Path(tmpdir)))
            add_strategy_experiment(
                config,
                strategy_id="volume spike retest",
                version="v1",
                hypothesis="volume spike after sweep improves entry timing",
                status="PAPER",
                backtest_score=30,
                paper_score=25,
                evidence_score=20,
                risk_score=5,
            )
            add_strategy_experiment(
                config,
                strategy_id="weak chop filter",
                version="v1",
                hypothesis="sideways filter needs proof",
                status="IDEA",
                risk_score=10,
            )

            report = build_experiment_scoreboard(config)
            path = save_experiment_scoreboard(report, config.data_root)

            self.assertEqual("EXPERIMENT_SCOREBOARD_ACTIVE", report.status)
            self.assertEqual("volume_spike_retest v1", report.top_strategy)
            self.assertEqual("PAPER_CANDIDATE", report.rows[0].recommendation)
            self.assertTrue(path.exists())

    def test_rejects_unknown_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_config(_write_config(Path(tmpdir)))

            with self.assertRaises(ValueError):
                add_strategy_experiment(config, "x", "v1", "idea", status="LIVE")


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


if __name__ == "__main__":
    unittest.main()
