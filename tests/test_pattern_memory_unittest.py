from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from trading_bot.config import load_config
from trading_bot.research import build_pattern_memory_report, save_pattern_memory_report
from trading_bot.storage import init_database


class PatternMemoryTest(unittest.TestCase):
    def test_pattern_memory_needs_database_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")
            config = load_config(config_path)

            report = build_pattern_memory_report(config)

        self.assertEqual("PATTERN_MEMORY_NEEDS_DATABASE", report.status)
        self.assertIn("never place live orders", report.guardrail)

    def test_pattern_memory_combines_trade_outcome_and_manual_label(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            db_path = data_root / "bot.sqlite3"
            _write_config(config_path, data_root)
            config = load_config(config_path)
            init_database(db_path)
            _insert_candles(db_path, count=80)
            _insert_paper_trades(db_path)
            label_path = data_root / "reports" / "learning" / "manual_labels.json"
            _write_json(
                label_path,
                {
                    "labels": [
                        {
                            "symbol": "BTC/USDT",
                            "timeframe": "15m",
                            "label": "good_retest_after_sweep",
                            "note": "entry valid tapi tunggu volume confirmation",
                        }
                    ]
                },
            )

            report = build_pattern_memory_report(config, db_path=db_path, label_path=label_path, limit=80)
            path = save_pattern_memory_report(report, config.data_root)
            path_exists = path.exists()

        self.assertTrue(path_exists)
        self.assertEqual("PATTERN_MEMORY_ACTIVE", report.status)
        self.assertEqual(1, report.row_count)
        self.assertEqual(2, report.total_trades)
        self.assertEqual(1, report.total_labels)
        self.assertEqual("NEEDS_MORE_TRADES", report.rows[0].outcome_grade)
        self.assertIn("good_retest_after_sweep", report.rows[0].labels)


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


def _insert_candles(db_path: Path, count: int) -> None:
    with sqlite3.connect(db_path) as connection:
        for index in range(count):
            base = 100 + index
            connection.execute(
                """
                INSERT INTO market_candles (
                    symbol, timeframe, open_time_ms, open, high, low, close, volume, close_time_ms, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "BTC/USDT",
                    "15m",
                    1_710_000_000_000 + index * 900_000,
                    base,
                    base * 1.01,
                    base * 0.99,
                    base * 1.005,
                    10 + (index % 7),
                    1_710_000_899_999 + index * 900_000,
                    "unit",
                ),
            )
        connection.commit()


def _insert_paper_trades(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        rows = [
            (1_710_000_000_000, 1_710_000_900_000, 100, 102, 0.1, 0.2, 0.01, 0.19, "take_profit"),
            (1_710_000_900_000, 1_710_001_800_000, 102, 101, 0.1, -0.1, 0.01, -0.11, "stop_loss"),
        ]
        for row in rows:
            connection.execute(
                """
                INSERT INTO paper_trades (
                    symbol, timeframe, entry_time_ms, exit_time_ms, entry_price, exit_price,
                    quantity, gross_pnl, fees, net_pnl, exit_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("BTC/USDT", "15m", *row),
            )
        connection.commit()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
