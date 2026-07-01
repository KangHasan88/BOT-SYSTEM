from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from trading_bot.research import generate_database_learning_snapshot, save_database_learning_snapshot
from trading_bot.storage import init_database, load_candles_from_database


class DatabaseLearningTest(unittest.TestCase):
    def test_load_candles_from_database_filters_symbol_timeframe(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "bot.sqlite3"
            init_database(db_path)
            _insert_candles(db_path, "BTC/USDT", "15m", count=60)
            _insert_candles(db_path, "ETH/USDT", "15m", count=10)

            candles = load_candles_from_database(db_path, symbol="BTC/USDT", timeframe="15m", limit=50)

        self.assertEqual(50, len(candles))
        self.assertTrue(all(candle.symbol == "BTC/USDT" for candle in candles))
        self.assertLess(candles[0].open_time_ms, candles[-1].open_time_ms)

    def test_generate_database_learning_snapshot_reports_observation(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            db_path = root / "bot.sqlite3"
            init_database(db_path)
            _insert_candles(db_path, "BTC/USDT", "15m", count=80)

            snapshot = generate_database_learning_snapshot(db_path, ["BTC/USDT"], ["15m"], limit=80)
            path = save_database_learning_snapshot(snapshot, root)

            self.assertTrue(path.exists())
            self.assertEqual(1, len(snapshot.rows))
            self.assertEqual("BTC/USDT", snapshot.rows[0].symbol)
            self.assertEqual(80, snapshot.rows[0].candle_count)
            self.assertTrue(snapshot.notes)

    def test_generate_database_learning_snapshot_handles_missing_data(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "missing.sqlite3"

            snapshot = generate_database_learning_snapshot(db_path, ["BTC/USDT"], ["15m"], limit=80)

        self.assertEqual("NO_DATA", snapshot.rows[0].observation)
        self.assertIn("database belum punya candle market", snapshot.notes[0])


def _insert_candles(db_path: Path, symbol: str, timeframe: str, count: int) -> None:
    with sqlite3.connect(db_path) as connection:
        for index in range(count):
            base = 100 + index
            volume = 10 + (index % 5)
            connection.execute(
                """
                INSERT INTO market_candles (
                    symbol, timeframe, open_time_ms, open, high, low, close, volume, close_time_ms, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    timeframe,
                    1_710_000_000_000 + index * 900_000,
                    base,
                    base * 1.01,
                    base * 0.99,
                    base * 1.005,
                    volume,
                    1_710_000_899_999 + index * 900_000,
                    "unit",
                ),
            )
        connection.commit()


if __name__ == "__main__":
    unittest.main()
