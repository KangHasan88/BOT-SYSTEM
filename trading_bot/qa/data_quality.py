from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.data_collector.audit import build_quality_report
from trading_bot.data_collector.models import Candle
from trading_bot.data_collector.timeframes import timeframe_to_ms


@dataclass(frozen=True)
class DataQualityGateConfig:
    max_gap_count: int = 0
    max_duplicate_count: int = 0
    max_non_positive_price_count: int = 0
    max_high_low_violation_count: int = 0
    max_zero_volume_pct: float = 5.0
    max_stale_candles: int = 3


@dataclass(frozen=True)
class DataQualityGateReport:
    symbol: str
    timeframe: str
    status: str
    candle_count: int
    gap_count: int
    duplicate_count: int
    zero_volume_count: int
    zero_volume_pct: float
    non_positive_price_count: int
    high_low_violation_count: int
    stale_candles: int | None
    dataset_id: str
    generated_at_utc: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def evaluate_data_quality_gate(
    candles: list[Candle],
    symbol: str,
    timeframe: str,
    now_ms: int | None = None,
    config: DataQualityGateConfig | None = None,
) -> DataQualityGateReport:
    gate_config = config or DataQualityGateConfig()
    quality = build_quality_report(candles, symbol, timeframe)
    high_low_violations = sum(1 for candle in candles if candle.high < candle.low)
    stale_candles = _stale_candles(quality.last_open_time_ms, timeframe, now_ms)
    zero_volume_pct = _pct(quality.zero_volume_count, quality.candle_count)
    blockers: list[str] = []
    warnings: list[str] = []

    if quality.candle_count == 0:
        blockers.append("candle_count is 0")
    if quality.gap_count > gate_config.max_gap_count:
        blockers.append(f"gap_count {quality.gap_count} > allowed {gate_config.max_gap_count}")
    if quality.duplicate_count > gate_config.max_duplicate_count:
        blockers.append(
            f"duplicate_count {quality.duplicate_count} > allowed {gate_config.max_duplicate_count}"
        )
    if quality.non_positive_price_count > gate_config.max_non_positive_price_count:
        blockers.append(
            "non_positive_price_count "
            f"{quality.non_positive_price_count} > allowed {gate_config.max_non_positive_price_count}"
        )
    if high_low_violations > gate_config.max_high_low_violation_count:
        blockers.append(
            "high_low_violation_count "
            f"{high_low_violations} > allowed {gate_config.max_high_low_violation_count}"
        )
    if stale_candles is not None and stale_candles > gate_config.max_stale_candles:
        blockers.append(f"stale_candles {stale_candles} > allowed {gate_config.max_stale_candles}")
    if zero_volume_pct > gate_config.max_zero_volume_pct:
        warnings.append(
            f"zero_volume_pct {zero_volume_pct:.2f}% > review threshold "
            f"{gate_config.max_zero_volume_pct:.2f}%"
        )

    return DataQualityGateReport(
        symbol=symbol,
        timeframe=timeframe,
        status="BLOCKED" if blockers else "WARN" if warnings else "PASSED",
        candle_count=quality.candle_count,
        gap_count=quality.gap_count,
        duplicate_count=quality.duplicate_count,
        zero_volume_count=quality.zero_volume_count,
        zero_volume_pct=zero_volume_pct,
        non_positive_price_count=quality.non_positive_price_count,
        high_low_violation_count=high_low_violations,
        stale_candles=stale_candles,
        dataset_id=quality.dataset_id,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        blockers=blockers,
        warnings=warnings,
    )


def save_data_quality_gate_report(report: DataQualityGateReport, root: str | Path) -> Path:
    path = (
        Path(root)
        / "qa"
        / "data_quality_gate"
        / report.symbol.replace("/", "_")
        / report.timeframe
        / "report.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _stale_candles(last_open_time_ms: int | None, timeframe: str, now_ms: int | None) -> int | None:
    if last_open_time_ms is None or now_ms is None:
        return None
    step_ms = timeframe_to_ms(timeframe)
    if now_ms <= last_open_time_ms:
        return 0
    return max(0, int((now_ms - last_open_time_ms) // step_ms) - 1)


def _pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return (part / whole) * 100.0
