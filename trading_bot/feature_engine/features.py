from __future__ import annotations

from dataclasses import dataclass

from trading_bot.data_collector.models import Candle
from trading_bot.feature_engine.indicators import atr, ema, rsi, sma


@dataclass(frozen=True)
class FeatureRow:
    symbol: str
    timeframe: str
    open_time_ms: int
    close: float
    ema_fast: float | None
    ema_slow: float | None
    rsi: float | None
    atr: float | None
    volume_sma: float | None
    body_pct: float
    upper_wick_pct: float
    lower_wick_pct: float
    range_pct: float
    volume_spike_ratio: float | None


@dataclass(frozen=True)
class FeatureConfig:
    ema_fast_period: int = 12
    ema_slow_period: int = 26
    rsi_period: int = 14
    atr_period: int = 14
    volume_sma_period: int = 20


def build_features(candles: list[Candle], config: FeatureConfig | None = None) -> list[FeatureRow]:
    if config is None:
        config = FeatureConfig()

    ordered = sorted(candles, key=lambda candle: candle.open_time_ms)
    closes = [candle.close for candle in ordered]
    highs = [candle.high for candle in ordered]
    lows = [candle.low for candle in ordered]
    volumes = [candle.volume for candle in ordered]

    ema_fast_values = ema(closes, config.ema_fast_period)
    ema_slow_values = ema(closes, config.ema_slow_period)
    rsi_values = rsi(closes, config.rsi_period)
    atr_values = atr(highs, lows, closes, config.atr_period)
    volume_sma_values = sma(volumes, config.volume_sma_period)

    rows: list[FeatureRow] = []
    for index, candle in enumerate(ordered):
        candle_range = candle.high - candle.low
        body = abs(candle.close - candle.open)
        upper_wick = candle.high - max(candle.open, candle.close)
        lower_wick = min(candle.open, candle.close) - candle.low
        denominator = candle.close if candle.close else 1
        volume_sma = volume_sma_values[index]

        rows.append(
            FeatureRow(
                symbol=candle.symbol,
                timeframe=candle.timeframe,
                open_time_ms=candle.open_time_ms,
                close=candle.close,
                ema_fast=ema_fast_values[index],
                ema_slow=ema_slow_values[index],
                rsi=rsi_values[index],
                atr=atr_values[index],
                volume_sma=volume_sma,
                body_pct=(body / denominator) * 100,
                upper_wick_pct=(upper_wick / denominator) * 100,
                lower_wick_pct=(lower_wick / denominator) * 100,
                range_pct=(candle_range / denominator) * 100,
                volume_spike_ratio=(candle.volume / volume_sma) if volume_sma else None,
            )
        )

    return rows
