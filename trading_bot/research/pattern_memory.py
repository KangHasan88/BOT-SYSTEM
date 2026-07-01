from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig
from trading_bot.research.database_learning import generate_database_learning_snapshot
from trading_bot.storage import default_database_path


@dataclass(frozen=True)
class ManualPatternLabel:
    symbol: str
    timeframe: str
    label: str
    note: str
    confidence: str = "manual"


@dataclass(frozen=True)
class PatternMemoryRow:
    symbol: str
    timeframe: str
    observation: str
    label_count: int
    labels: list[str]
    trade_count: int
    win_rate_pct: float
    total_net_pnl: float
    average_net_pnl: float
    best_trade_pnl: float
    worst_trade_pnl: float
    outcome_grade: str
    lesson: str
    next_action: str


@dataclass(frozen=True)
class PatternMemoryReport:
    status: str
    generated_at_utc: str
    db_path: str
    label_path: str
    row_count: int
    total_trades: int
    total_labels: int
    summary: str
    guardrail: str
    rows: list[PatternMemoryRow] = field(default_factory=list)


def build_pattern_memory_report(
    config: BotConfig,
    db_path: str | Path | None = None,
    label_path: str | Path | None = None,
    limit: int = 500,
) -> PatternMemoryReport:
    root = Path(config.data_root)
    database = Path(db_path) if db_path is not None else default_database_path(root)
    labels_file = Path(label_path) if label_path is not None else root / "reports" / "learning" / "manual_labels.json"
    labels = _load_manual_labels(labels_file)

    if not database.exists():
        return PatternMemoryReport(
            status="PATTERN_MEMORY_NEEDS_DATABASE",
            generated_at_utc=_now(),
            db_path=str(database),
            label_path=str(labels_file),
            row_count=0,
            total_trades=0,
            total_labels=len(labels),
            summary="database belum tersedia; jalankan Import DB dulu",
            guardrail="Pattern memory is for review only and must never place live orders.",
            rows=[],
        )

    learning = generate_database_learning_snapshot(database, config.symbols, config.timeframes, limit=limit)
    trade_stats = _paper_trade_stats(database)
    labels_by_pair = _labels_by_pair(labels)
    rows: list[PatternMemoryRow] = []
    for learning_row in learning.rows:
        key = (learning_row.symbol, learning_row.timeframe)
        stats = trade_stats.get(key, _empty_trade_stats())
        row_labels = labels_by_pair.get(key, [])
        rows.append(_memory_row(learning_row.symbol, learning_row.timeframe, learning_row.observation, stats, row_labels))

    total_trades = sum(row.trade_count for row in rows)
    status = "PATTERN_MEMORY_ACTIVE" if rows and (total_trades > 0 or labels) else "PATTERN_MEMORY_NEEDS_REVIEW"
    return PatternMemoryReport(
        status=status,
        generated_at_utc=_now(),
        db_path=str(database),
        label_path=str(labels_file),
        row_count=len(rows),
        total_trades=total_trades,
        total_labels=len(labels),
        summary=_summary(status, total_trades, len(labels)),
        guardrail="Pattern memory is for review only and must never place live orders.",
        rows=rows,
    )


def save_pattern_memory_report(report: PatternMemoryReport, root: str | Path) -> Path:
    path = Path(root) / "reports" / "learning" / "pattern_memory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _paper_trade_stats(db_path: Path) -> dict[tuple[str, str], dict[str, float | int]]:
    query = """
        SELECT symbol, timeframe, COUNT(*), SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END),
               SUM(net_pnl), AVG(net_pnl), MAX(net_pnl), MIN(net_pnl)
        FROM paper_trades
        GROUP BY symbol, timeframe
    """
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(query).fetchall()
    return {
        (str(row[0]), str(row[1])): {
            "trade_count": int(row[2] or 0),
            "win_count": int(row[3] or 0),
            "total_net_pnl": float(row[4] or 0.0),
            "average_net_pnl": float(row[5] or 0.0),
            "best_trade_pnl": float(row[6] or 0.0),
            "worst_trade_pnl": float(row[7] or 0.0),
        }
        for row in rows
    }


def _memory_row(
    symbol: str,
    timeframe: str,
    observation: str,
    stats: dict[str, float | int],
    labels: list[ManualPatternLabel],
) -> PatternMemoryRow:
    trade_count = int(stats["trade_count"])
    win_count = int(stats["win_count"])
    total_net_pnl = float(stats["total_net_pnl"])
    win_rate = (win_count / trade_count) * 100 if trade_count else 0.0
    grade = _outcome_grade(trade_count, win_rate, total_net_pnl)
    return PatternMemoryRow(
        symbol=symbol,
        timeframe=timeframe,
        observation=observation,
        label_count=len(labels),
        labels=[label.label for label in labels],
        trade_count=trade_count,
        win_rate_pct=win_rate,
        total_net_pnl=total_net_pnl,
        average_net_pnl=float(stats["average_net_pnl"]),
        best_trade_pnl=float(stats["best_trade_pnl"]),
        worst_trade_pnl=float(stats["worst_trade_pnl"]),
        outcome_grade=grade,
        lesson=_lesson(observation, grade, labels),
        next_action=_next_action(trade_count, labels, grade),
    )


def _outcome_grade(trade_count: int, win_rate_pct: float, total_net_pnl: float) -> str:
    if trade_count == 0:
        return "NO_TRADES"
    if trade_count < 20:
        return "NEEDS_MORE_TRADES"
    if total_net_pnl > 0 and win_rate_pct >= 45:
        return "PROMISING"
    if total_net_pnl <= 0:
        return "WEAK"
    return "MIXED"


def _lesson(observation: str, grade: str, labels: list[ManualPatternLabel]) -> str:
    if labels:
        return f"manual review: {labels[-1].label} - {labels[-1].note}"
    if grade == "PROMISING":
        return f"{observation} punya outcome paper positif; tetap tunggu evidence stabil"
    if grade == "WEAK":
        return f"{observation} belum layak dipromosikan; review filter entry/exit"
    if grade == "NEEDS_MORE_TRADES":
        return f"{observation} butuh minimal 20 paper trade sebelum dinilai"
    return f"{observation} belum punya cukup outcome"


def _next_action(trade_count: int, labels: list[ManualPatternLabel], grade: str) -> str:
    if not labels:
        return "Tambahkan label manual setelah review chart/trade"
    if trade_count < 20:
        return "Lanjutkan paper campaign sampai minimal 20 trade"
    if grade == "PROMISING":
        return "Masukkan ke kandidat eksperimen, bukan live order"
    return "Review mistake tag dan perbaiki filter"


def _load_manual_labels(path: Path) -> list[ManualPatternLabel]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    rows = payload.get("labels", []) if isinstance(payload, dict) else []
    labels: list[ManualPatternLabel] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        labels.append(
            ManualPatternLabel(
                symbol=str(row.get("symbol", "")),
                timeframe=str(row.get("timeframe", "")),
                label=str(row.get("label", "")),
                note=str(row.get("note", "")),
                confidence=str(row.get("confidence", "manual")),
            )
        )
    return [label for label in labels if label.symbol and label.timeframe and label.label]


def _labels_by_pair(labels: list[ManualPatternLabel]) -> dict[tuple[str, str], list[ManualPatternLabel]]:
    grouped: dict[tuple[str, str], list[ManualPatternLabel]] = defaultdict(list)
    for label in labels:
        grouped[(label.symbol, label.timeframe)].append(label)
    return dict(grouped)


def _empty_trade_stats() -> dict[str, float | int]:
    return {
        "trade_count": 0,
        "win_count": 0,
        "total_net_pnl": 0.0,
        "average_net_pnl": 0.0,
        "best_trade_pnl": 0.0,
        "worst_trade_pnl": 0.0,
    }


def _summary(status: str, total_trades: int, total_labels: int) -> str:
    if status == "PATTERN_MEMORY_ACTIVE":
        return f"pattern memory aktif: {total_trades} trade dan {total_labels} label manual terbaca"
    return "pattern memory butuh paper trade atau label manual"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
