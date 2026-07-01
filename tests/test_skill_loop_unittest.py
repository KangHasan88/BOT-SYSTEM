from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.config import load_config
from trading_bot.data_collector import Candle, CandleCsvStore
from trading_bot.research import build_skill_loop_report, save_skill_loop_report


class SkillLoopTest(unittest.TestCase):
    def test_skill_loop_needs_data_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")
            config = load_config(config_path)

            report = build_skill_loop_report(config)

        self.assertEqual("SKILL_LOOP_NEEDS_DATA", report.status)
        self.assertTrue(any(step.status == "TODO" for step in report.steps))
        self.assertIn("live orders", report.guardrail)

    def test_skill_loop_active_with_learning_and_paper_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            config = load_config(config_path)
            CandleCsvStore(data_root).upsert_many(_candles(80))
            _write_json(
                data_root / "reports" / "learning" / "database_snapshot.json",
                {"rows": [{"symbol": "BTC/USDT"}], "notes": ["BTC/USDT 15m: WATCH_VOLUME_SPIKE"]},
            )
            _write_json(data_root / "readiness" / "live_evidence.json", {"completion_pct": 50.0, "summary": "incomplete"})
            _write_json(
                data_root / "qa" / "paper_campaign" / "report.json",
                {"status": "PAPER_CAMPAIGN_COLLECTING", "summary": "collecting", "blockers": ["trade_count 1 < required 20"]},
            )
            paper_dir = data_root / "paper" / "BTC_USDT" / "15m"
            paper_dir.mkdir(parents=True)
            (paper_dir / "trades.csv").write_text(
                "symbol,timeframe,entry_time_ms,exit_time_ms,entry_price,exit_price,quantity,gross_pnl,fees,net_pnl,exit_reason\n"
                "BTC/USDT,15m,1,2,100,101,1,1,0,1,SESSION_END\n",
                encoding="utf-8",
            )

            report = build_skill_loop_report(config)
            path = save_skill_loop_report(report, config.data_root)
            path_exists = path.exists()

        self.assertTrue(path_exists)
        self.assertEqual("SKILL_LOOP_ACTIVE", report.status)
        self.assertEqual(80, report.candle_rows)
        self.assertEqual(1, report.paper_trades)
        self.assertGreater(len(report.experiment_candidates), 0)


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


def _candles(count: int) -> list[Candle]:
    return [
        Candle("BTC/USDT", "15m", (index + 1) * 900_000, 100 + index, 101 + index, 99 + index, 100.5 + index, 10)
        for index in range(count)
    ]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
