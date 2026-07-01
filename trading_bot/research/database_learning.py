from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.data_collector.models import Candle
from trading_bot.pattern_analyzer import detect_price_action_patterns
from trading_bot.storage import load_candles_from_database


@dataclass(frozen=True)
class MarketLearningRow:
    symbol: str
    timeframe: str
    candle_count: int
    first_open_time_ms: int | None
    last_open_time_ms: int | None
    average_range_pct: float
    average_volume: float
    latest_close: float | None
    latest_volume_ratio: float | None
    pattern_counts: dict[str, int]
    observation: str


@dataclass(frozen=True)
class DatabaseLearningSnapshot:
    generated_at_utc: str
    db_path: str
    limit: int
    rows: list[MarketLearningRow]
    notes: list[str]


def generate_database_learning_snapshot(
    db_path: str | Path,
    symbols: list[str],
    timeframes: list[str],
    limit: int = 500,
) -> DatabaseLearningSnapshot:
    rows: list[MarketLearningRow] = []
    for symbol in symbols:
        for timeframe in timeframes:
            candles = load_candles_from_database(db_path, symbol=symbol, timeframe=timeframe, limit=limit)
            rows.append(_learning_row(symbol, timeframe, candles))
    return DatabaseLearningSnapshot(
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        db_path=str(db_path),
        limit=limit,
        rows=rows,
        notes=_snapshot_notes(rows),
    )


def save_database_learning_snapshot(snapshot: DatabaseLearningSnapshot, root: str | Path) -> Path:
    path = Path(root) / "reports" / "learning" / "database_snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(snapshot), indent=2), encoding="utf-8")
    return path


def _learning_row(symbol: str, timeframe: str, candles: list[Candle]) -> MarketLearningRow:
    if not candles:
        return MarketLearningRow(
            symbol=symbol,
            timeframe=timeframe,
            candle_count=0,
            first_open_time_ms=None,
            last_open_time_ms=None,
            average_range_pct=0.0,
            average_volume=0.0,
            latest_close=None,
            latest_volume_ratio=None,
            pattern_counts={},
            observation="NO_DATA",
        )

    ranges = [((candle.high - candle.low) / candle.close) * 100 for candle in candles if candle.close > 0]
    volumes = [candle.volume for candle in candles]
    avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
    latest = candles[-1]
    latest_volume_ratio = latest.volume / avg_volume if avg_volume else None
    patterns = detect_price_action_patterns(candles)
    pattern_counts = Counter(pattern.pattern for pattern in patterns)

    return MarketLearningRow(
        symbol=symbol,
        timeframe=timeframe,
        candle_count=len(candles),
        first_open_time_ms=candles[0].open_time_ms,
        last_open_time_ms=latest.open_time_ms,
        average_range_pct=sum(ranges) / len(ranges) if ranges else 0.0,
        average_volume=avg_volume,
        latest_close=latest.close,
        latest_volume_ratio=latest_volume_ratio,
        pattern_counts=dict(pattern_counts),
        observation=_observation(len(candles), latest_volume_ratio, pattern_counts),
    )


def _observation(candle_count: int, latest_volume_ratio: float | None, pattern_counts: Counter) -> str:
    if candle_count < 50:
        return "NEED_MORE_DATA"
    if pattern_counts.get("absorption_candidate", 0) >= 3:
        return "WATCH_ABSORPTION"
    if pattern_counts.get("sweep_up", 0) or pattern_counts.get("sweep_down", 0):
        return "WATCH_LIQUIDITY_SWEEP"
    if latest_volume_ratio is not None and latest_volume_ratio >= 1.8:
        return "WATCH_VOLUME_SPIKE"
    return "NORMAL_OBSERVATION"


def _snapshot_notes(rows: list[MarketLearningRow]) -> list[str]:
    if not rows or all(row.candle_count == 0 for row in rows):
        return ["database belum punya candle market; jalankan Sync lalu Import DB"]
    notes: list[str] = []
    for row in rows:
        if row.observation != "NORMAL_OBSERVATION":
            notes.append(f"{row.symbol} {row.timeframe}: {row.observation}")
    if not notes:
        notes.append("belum ada pola khusus; lanjut kumpulkan data")
    return notes
