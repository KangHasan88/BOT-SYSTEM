from __future__ import annotations

import hashlib
import json

from trading_bot.data_collector.models import Candle, Gap, QualityReport
from trading_bot.data_collector.timeframes import timeframe_to_ms


def find_gaps(candles: list[Candle]) -> list[Gap]:
    if len(candles) < 2:
        return []

    ordered = sorted(candles, key=lambda candle: candle.open_time_ms)
    symbol = ordered[0].symbol
    timeframe = ordered[0].timeframe
    step_ms = timeframe_to_ms(timeframe)
    gaps: list[Gap] = []

    for previous, current in zip(ordered, ordered[1:]):
        expected = previous.open_time_ms + step_ms
        while expected < current.open_time_ms:
            gaps.append(
                Gap(
                    symbol=symbol,
                    timeframe=timeframe,
                    missing_open_time_ms=expected,
                    previous_open_time_ms=previous.open_time_ms,
                    next_open_time_ms=current.open_time_ms,
                )
            )
            expected += step_ms

    return gaps


def build_quality_report(candles: list[Candle], symbol: str, timeframe: str) -> QualityReport:
    ordered = sorted(candles, key=lambda candle: candle.open_time_ms)
    seen: set[int] = set()
    duplicate_count = 0
    zero_volume_count = 0
    non_positive_price_count = 0

    for candle in ordered:
        if candle.open_time_ms in seen:
            duplicate_count += 1
        seen.add(candle.open_time_ms)
        if candle.volume == 0:
            zero_volume_count += 1
        if min(candle.open, candle.high, candle.low, candle.close) <= 0:
            non_positive_price_count += 1

    gaps = find_gaps(ordered)
    dataset_id = compute_dataset_id(ordered)

    return QualityReport(
        symbol=symbol,
        timeframe=timeframe,
        candle_count=len(ordered),
        first_open_time_ms=ordered[0].open_time_ms if ordered else None,
        last_open_time_ms=ordered[-1].open_time_ms if ordered else None,
        gap_count=len(gaps),
        duplicate_count=duplicate_count,
        zero_volume_count=zero_volume_count,
        non_positive_price_count=non_positive_price_count,
        dataset_id=dataset_id,
    )


def compute_dataset_id(candles: list[Candle]) -> str:
    payload = [
        [
            candle.symbol,
            candle.timeframe,
            candle.open_time_ms,
            candle.open,
            candle.high,
            candle.low,
            candle.close,
            candle.volume,
        ]
        for candle in sorted(candles, key=lambda item: item.open_time_ms)
    ]
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
