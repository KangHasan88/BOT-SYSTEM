from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.config import load_config
from trading_bot.research import add_human_feedback_label, build_human_feedback_report, save_human_feedback_report


class HumanFeedbackTest(unittest.TestCase):
    def test_feedback_report_empty_without_labels(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")
            config = load_config(config_path)

            report = build_human_feedback_report(config)

        self.assertEqual("HUMAN_FEEDBACK_EMPTY", report.status)
        self.assertIn("never place live orders", report.guardrail)
        self.assertIn("entry_telat", report.allowed_labels)

    def test_add_feedback_label_and_build_lessons(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            config = load_config(config_path)

            feedback = add_human_feedback_label(
                config,
                symbol="BTC/USDT",
                timeframe="15m",
                label="entry telat",
                note="entry terlalu jauh dari trigger",
                reviewer="hasan",
            )
            report = build_human_feedback_report(config)
            path = save_human_feedback_report(report, config.data_root)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual("entry_telat", feedback.label)
        self.assertEqual("HUMAN_FEEDBACK_ACTIVE", report.status)
        self.assertEqual(1, report.total_labels)
        self.assertEqual("entry_telat", report.top_label)
        self.assertEqual("entry_telat", report.lessons[0].label)
        self.assertEqual("HUMAN_FEEDBACK_ACTIVE", payload["status"])

    def test_rejects_unknown_label(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")
            config = load_config(config_path)

            with self.assertRaises(ValueError):
                add_human_feedback_label(config, "BTC/USDT", "15m", "asal label", "")


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
