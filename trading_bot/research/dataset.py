from __future__ import annotations

from dataclasses import dataclass

from trading_bot.data_collector.models import Candle
from trading_bot.pattern_analyzer.patterns import PatternSignal


@dataclass(frozen=True)
class PatternOutcomeRow:
    symbol: str
    timeframe: str
    open_time_ms: int
    pattern: str
    direction: str
    score: float
    entry_price: float
    horizon_candles: int
    max_favorable_pct: float
    max_adverse_pct: float
    close_return_pct: float
    outcome_label: str
    manual_label: str
    reason: str


def build_pattern_outcome_dataset(
    candles: list[Candle],
    patterns: list[PatternSignal],
    horizon_candles: int = 12,
) -> list[PatternOutcomeRow]:
    if horizon_candles < 1:
        raise ValueError("horizon_candles must be >= 1")

    ordered = sorted(candles, key=lambda candle: candle.open_time_ms)
    candle_by_time = {candle.open_time_ms: candle for candle in ordered}
    index_by_time = {candle.open_time_ms: index for index, candle in enumerate(ordered)}
    rows: list[PatternOutcomeRow] = []

    for pattern in sorted(patterns, key=lambda item: item.open_time_ms):
        current = candle_by_time.get(pattern.open_time_ms)
        current_index = index_by_time.get(pattern.open_time_ms)
        if current is None or current_index is None:
            continue
        future = ordered[current_index + 1 : current_index + 1 + horizon_candles]
        if not future:
            continue

        direction = _direction_for_pattern(pattern.pattern)
        entry_price = current.close
        if direction == "long":
            favorable_pct = ((max(candle.high for candle in future) - entry_price) / entry_price) * 100
            adverse_pct = ((min(candle.low for candle in future) - entry_price) / entry_price) * 100
            close_return_pct = ((future[-1].close - entry_price) / entry_price) * 100
        else:
            favorable_pct = ((entry_price - min(candle.low for candle in future)) / entry_price) * 100
            adverse_pct = ((entry_price - max(candle.high for candle in future)) / entry_price) * 100
            close_return_pct = ((entry_price - future[-1].close) / entry_price) * 100

        rows.append(
            PatternOutcomeRow(
                symbol=pattern.symbol,
                timeframe=pattern.timeframe,
                open_time_ms=pattern.open_time_ms,
                pattern=pattern.pattern,
                direction=direction,
                score=pattern.score,
                entry_price=entry_price,
                horizon_candles=len(future),
                max_favorable_pct=favorable_pct,
                max_adverse_pct=adverse_pct,
                close_return_pct=close_return_pct,
                outcome_label=_outcome_label(favorable_pct, adverse_pct, close_return_pct),
                manual_label="",
                reason=pattern.reason,
            )
        )

    return rows


def _direction_for_pattern(pattern: str) -> str:
    if pattern in {"sweep_down", "false_breakout_down"}:
        return "long"
    if pattern in {"sweep_up", "false_breakout_up"}:
        return "short_watch"
    return "observe"


def _outcome_label(favorable_pct: float, adverse_pct: float, close_return_pct: float) -> str:
    if favorable_pct >= 1.0 and adverse_pct > -1.0 and close_return_pct > 0:
        return "GOOD_FOLLOW_THROUGH"
    if adverse_pct <= -1.0 and close_return_pct < 0:
        return "FAILED"
    if favorable_pct >= 0.5 and close_return_pct >= 0:
        return "PARTIAL_FOLLOW_THROUGH"
    return "NO_EDGE"
