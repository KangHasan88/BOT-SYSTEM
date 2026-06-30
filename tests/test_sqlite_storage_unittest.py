from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from trading_bot.storage import import_runtime_data, init_database, load_database_status


class SqliteStorageTest(unittest.TestCase):
    def test_init_database_creates_core_tables(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "bot.sqlite3"

            init_database(db_path)

            tables = _table_names(db_path)

        self.assertIn("market_candles", tables)
        self.assertIn("paper_trades", tables)
        self.assertIn("audit_events", tables)
        self.assertIn("orchestrator_activity", tables)

    def test_import_runtime_data_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir) / "data"
            db_path = Path(tmpdir) / "bot.sqlite3"
            _write_runtime_files(root)

            first = import_runtime_data(root, db_path)
            second = import_runtime_data(root, db_path)

            counts = _table_counts(
                db_path,
                [
                    "market_candles",
                    "paper_orders",
                    "paper_trades",
                    "paper_account_snapshots",
                    "audit_events",
                    "orchestrator_activity",
                ],
            )

        self.assertEqual(6, first.total_rows)
        self.assertEqual(0, second.total_rows)
        self.assertEqual(1, counts["market_candles"])
        self.assertEqual(1, counts["paper_orders"])
        self.assertEqual(1, counts["paper_trades"])
        self.assertEqual(1, counts["paper_account_snapshots"])
        self.assertEqual(1, counts["audit_events"])
        self.assertEqual(1, counts["orchestrator_activity"])

    def test_database_status_reports_counts(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir) / "data"
            db_path = Path(tmpdir) / "bot.sqlite3"
            _write_runtime_files(root)
            import_runtime_data(root, db_path)

            status = load_database_status(root, db_path)

        counts = {table.table: table.rows for table in status.tables}
        self.assertTrue(status.exists)
        self.assertGreater(status.size_bytes, 0)
        self.assertEqual(6, status.total_rows)
        self.assertEqual(1, counts["market_candles"])
        self.assertEqual(1, counts["orchestrator_activity"])


def _write_runtime_files(root: Path) -> None:
    candle_path = root / "BTC_USDT" / "15m.csv"
    candle_path.parent.mkdir(parents=True, exist_ok=True)
    candle_path.write_text(
        "symbol,timeframe,open_time_ms,open,high,low,close,volume,close_time_ms,source\n"
        "BTC/USDT,15m,1710000000000,100,110,95,105,12,1710000899999,unit\n",
        encoding="utf-8",
    )

    paper_path = root / "paper" / "BTC_USDT" / "15m"
    paper_path.mkdir(parents=True, exist_ok=True)
    (paper_path / "orders.csv").write_text(
        "symbol,timeframe,open_time_ms,side,action,price,quantity,notional,fee,status,reason\n"
        "BTC/USDT,15m,1710000000000,buy,OPEN,100,0.1,10,0.01,FILLED,unit\n",
        encoding="utf-8",
    )
    (paper_path / "trades.csv").write_text(
        "symbol,timeframe,entry_time_ms,exit_time_ms,entry_price,exit_price,quantity,gross_pnl,fees,net_pnl,exit_reason\n"
        "BTC/USDT,15m,1710000000000,1710000900000,100,105,0.1,0.5,0.02,0.48,take_profit\n",
        encoding="utf-8",
    )
    (paper_path / "account.csv").write_text(
        "open_time_ms,equity,day_start_equity,month_start_equity,open_positions,consecutive_losses_today,trading_status,status_reason\n"
        "1710000000000,1000.48,1000,1000,0,0,ACTIVE,unit\n",
        encoding="utf-8",
    )

    audit_path = root / "logs" / "audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(
            {
                "event": "cycle_start",
                "level": "INFO",
                "message": "started",
                "created_at_utc": "2026-06-30T00:00:00+00:00",
                "context": {"symbol": "BTC/USDT"},
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    activity_path = root / "orchestrator" / "activity.jsonl"
    activity_path.parent.mkdir(parents=True, exist_ok=True)
    activity_path.write_text(
        json.dumps(
            {
                "action": "validate_config",
                "status": "SUCCESS",
                "exit_code": 0,
                "output": "config ok",
                "created_at_utc": "2026-06-30T00:01:00+00:00",
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def _table_names(db_path: Path) -> set[str]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {str(row[0]) for row in rows}
    finally:
        connection.close()


def _table_counts(db_path: Path, tables: list[str]) -> dict[str, int]:
    connection = sqlite3.connect(db_path)
    try:
        counts: dict[str, int] = {}
        for table in tables:
            counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return counts
    finally:
        connection.close()


if __name__ == "__main__":
    unittest.main()
