from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from trading_bot.data_collector.models import Candle


@dataclass(frozen=True)
class DatabaseImportSummary:
    db_path: str
    candles: int
    paper_orders: int
    paper_trades: int
    paper_account_snapshots: int
    audit_events: int
    orchestrator_activities: int

    @property
    def total_rows(self) -> int:
        return (
            self.candles
            + self.paper_orders
            + self.paper_trades
            + self.paper_account_snapshots
            + self.audit_events
            + self.orchestrator_activities
        )


@dataclass(frozen=True)
class DatabaseTableSummary:
    table: str
    rows: int


@dataclass(frozen=True)
class DatabaseStatus:
    db_path: str
    exists: bool
    size_bytes: int
    updated_at_utc: str
    tables: list[DatabaseTableSummary]

    @property
    def total_rows(self) -> int:
        return sum(table.rows for table in self.tables)


def default_database_path(data_root: str | Path) -> Path:
    return Path(data_root) / "bot.sqlite3"


def init_database(db_path: str | Path, schema_path: str | Path = "database/schema.sql") -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = Path(schema_path).read_text(encoding="utf-8")
    with sqlite3.connect(path) as connection:
        connection.executescript(schema)
        _ensure_column(connection, "paper_account_snapshots", "unrealized_pnl", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "paper_account_snapshots", "marked_equity", "REAL NOT NULL DEFAULT 0")
        _create_idempotency_indexes(connection)
        connection.commit()
    return path


def import_runtime_data(
    data_root: str | Path,
    db_path: str | Path | None = None,
    schema_path: str | Path = "database/schema.sql",
) -> DatabaseImportSummary:
    root = Path(data_root)
    database = Path(db_path) if db_path is not None else default_database_path(root)
    init_database(database, schema_path)
    with sqlite3.connect(database) as connection:
        summary = DatabaseImportSummary(
            db_path=str(database),
            candles=_import_candles(connection, root),
            paper_orders=_import_paper_orders(connection, root),
            paper_trades=_import_paper_trades(connection, root),
            paper_account_snapshots=_import_paper_account(connection, root),
            audit_events=_import_audit_events(connection, root),
            orchestrator_activities=_import_orchestrator_activities(connection, root),
        )
        connection.commit()
    return summary


def load_database_status(data_root: str | Path, db_path: str | Path | None = None) -> DatabaseStatus:
    database = Path(db_path) if db_path is not None else default_database_path(data_root)
    if not database.exists():
        return DatabaseStatus(str(database), False, 0, "", [])

    stat = database.stat()
    tables = [
        "market_candles",
        "paper_orders",
        "paper_trades",
        "paper_account_snapshots",
        "audit_events",
        "orchestrator_activity",
    ]
    with sqlite3.connect(database) as connection:
        summaries = [
            DatabaseTableSummary(table=table, rows=_table_count(connection, table))
            for table in tables
            if _table_exists(connection, table)
        ]
    return DatabaseStatus(
        db_path=str(database),
        exists=True,
        size_bytes=stat.st_size,
        updated_at_utc=_utc_from_timestamp(stat.st_mtime),
        tables=summaries,
    )


def load_candles_from_database(
    db_path: str | Path,
    symbol: str = "",
    timeframe: str = "",
    limit: int = 500,
) -> list[Candle]:
    database = Path(db_path)
    if not database.exists():
        return []
    clauses = []
    params: list[object] = []
    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol)
    if timeframe:
        clauses.append("timeframe = ?")
        params.append(timeframe)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = (
        "SELECT symbol, timeframe, open_time_ms, open, high, low, close, volume, close_time_ms, source "
        f"FROM market_candles {where} ORDER BY open_time_ms DESC LIMIT ?"
    )
    params.append(max(1, limit))
    with sqlite3.connect(database) as connection:
        rows = connection.execute(query, params).fetchall()
    candles = [
        Candle(
            symbol=str(row[0]),
            timeframe=str(row[1]),
            open_time_ms=int(row[2]),
            open=float(row[3]),
            high=float(row[4]),
            low=float(row[5]),
            close=float(row[6]),
            volume=float(row[7]),
            close_time_ms=int(row[8]) if row[8] is not None else None,
            source=str(row[9]),
        )
        for row in rows
    ]
    return sorted(candles, key=lambda candle: candle.open_time_ms)


def _create_idempotency_indexes(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_orders_unique_import
            ON paper_orders (symbol, timeframe, open_time_ms, side, action, status, reason);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_trades_unique_import
            ON paper_trades (symbol, timeframe, entry_time_ms, exit_time_ms, exit_reason);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_account_unique_import
            ON paper_account_snapshots (open_time_ms);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_events_unique_import
            ON audit_events (ts, level, event, message);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_orchestrator_activity_unique_import
            ON orchestrator_activity (ts, action, status, return_code);
        """
    )


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _table_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _utc_from_timestamp(timestamp: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="seconds")


def _import_candles(connection: sqlite3.Connection, root: Path) -> int:
    inserted = 0
    for path in root.glob("*/*.csv"):
        if path.parts[-2] in {"paper", "features", "patterns", "signals", "regimes", "research"}:
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if not {"symbol", "timeframe", "open_time_ms", "open", "high", "low", "close", "volume"}.issubset(row):
                    continue
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO market_candles (
                        symbol, timeframe, open_time_ms, open, high, low, close, volume, close_time_ms, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["symbol"],
                        row["timeframe"],
                        int(row["open_time_ms"]),
                        float(row["open"]),
                        float(row["high"]),
                        float(row["low"]),
                        float(row["close"]),
                        float(row["volume"]),
                        _optional_int(row.get("close_time_ms", "")),
                        row.get("source") or "unknown",
                    ),
                )
                inserted += cursor.rowcount
    return inserted


def _import_paper_orders(connection: sqlite3.Connection, root: Path) -> int:
    return _import_csv_rows(
        connection,
        root / "paper",
        "orders.csv",
        """
        INSERT OR IGNORE INTO paper_orders (
            symbol, timeframe, open_time_ms, side, action, price, quantity, notional, fee, status, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        lambda row: (
            row["symbol"],
            row["timeframe"],
            int(row["open_time_ms"]),
            row["side"],
            row["action"],
            float(row["price"]),
            float(row["quantity"]),
            float(row["notional"]),
            float(row["fee"]),
            row["status"],
            row["reason"],
        ),
    )


def _import_paper_trades(connection: sqlite3.Connection, root: Path) -> int:
    return _import_csv_rows(
        connection,
        root / "paper",
        "trades.csv",
        """
        INSERT OR IGNORE INTO paper_trades (
            symbol, timeframe, entry_time_ms, exit_time_ms, entry_price, exit_price,
            quantity, gross_pnl, fees, net_pnl, exit_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        lambda row: (
            row["symbol"],
            row["timeframe"],
            int(row["entry_time_ms"]),
            int(row["exit_time_ms"]),
            float(row["entry_price"]),
            float(row["exit_price"]),
            float(row["quantity"]),
            float(row["gross_pnl"]),
            float(row["fees"]),
            float(row["net_pnl"]),
            row["exit_reason"],
        ),
    )


def _import_paper_account(connection: sqlite3.Connection, root: Path) -> int:
    return _import_csv_rows(
        connection,
        root / "paper",
        "account.csv",
        """
        INSERT OR IGNORE INTO paper_account_snapshots (
            open_time_ms, equity, day_start_equity, month_start_equity,
            open_positions, consecutive_losses_today, trading_status, status_reason,
            unrealized_pnl, marked_equity
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        lambda row: (
            int(row["open_time_ms"]),
            float(row["equity"]),
            float(row["day_start_equity"]),
            float(row["month_start_equity"]),
            int(row["open_positions"]),
            int(row["consecutive_losses_today"]),
            row["trading_status"],
            row["status_reason"],
            float(row.get("unrealized_pnl", 0) or 0),
            float(row.get("marked_equity", row.get("equity", 0)) or 0),
        ),
    )


def _import_csv_rows(
    connection: sqlite3.Connection,
    root: Path,
    filename: str,
    statement: str,
    values_factory,
) -> int:
    inserted = 0
    if not root.exists():
        return 0
    for path in root.rglob(filename):
        if path.stat().st_size == 0:
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                cursor = connection.execute(statement, values_factory(row))
                inserted += cursor.rowcount
    return inserted


def _import_audit_events(connection: sqlite3.Connection, root: Path) -> int:
    path = root / "logs" / "audit.jsonl"
    if not path.exists():
        return 0
    inserted = 0
    for payload in _read_jsonl(path):
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO audit_events (ts, level, event, message, context_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(payload.get("created_at_utc", "")),
                str(payload.get("level", "")),
                str(payload.get("event", "")),
                str(payload.get("message", "")),
                json.dumps(payload.get("context", {}), separators=(",", ":")),
            ),
        )
        inserted += cursor.rowcount
    return inserted


def _import_orchestrator_activities(connection: sqlite3.Connection, root: Path) -> int:
    path = root / "orchestrator" / "activity.jsonl"
    if not path.exists():
        return 0
    inserted = 0
    for payload in _read_jsonl(path):
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO orchestrator_activity (
                ts, action, status, return_code, duration_ms, output_tail
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(payload.get("created_at_utc", "")),
                str(payload.get("action", "")),
                str(payload.get("status", "")),
                int(payload.get("exit_code", 0)),
                int(payload.get("duration_ms", 0)),
                str(payload.get("output", ""))[-6000:],
            ),
        )
        inserted += cursor.rowcount
    return inserted


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
