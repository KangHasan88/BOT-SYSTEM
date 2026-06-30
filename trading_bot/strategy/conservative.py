from __future__ import annotations

from trading_bot.feature_engine.features import FeatureRow
from trading_bot.feature_engine.regime import RegimeRow
from trading_bot.strategy.signals import Signal, SignalConfig


def generate_conservative_signals(
    features: list[FeatureRow],
    regimes: list[RegimeRow],
    config: SignalConfig | None = None,
) -> list[Signal]:
    if config is None:
        config = SignalConfig()

    regime_by_time = {row.open_time_ms: row for row in regimes}
    signals: list[Signal] = []

    for row in features:
        regime = regime_by_time.get(row.open_time_ms)
        if regime is None:
            signals.append(_skip(row, "missing regime context"))
            continue

        missing = _missing_feature_reason(row)
        if missing:
            signals.append(_skip(row, missing))
            continue

        assert row.ema_fast is not None
        assert row.ema_slow is not None
        assert row.rsi is not None

        if regime.regime in {"low_liquidity", "volatile"}:
            signals.append(_skip(row, f"unsafe regime: {regime.regime}"))
            continue

        if row.volume_spike_ratio is not None and row.volume_spike_ratio < config.min_volume_ratio:
            signals.append(_skip(row, f"volume too low: ratio={row.volume_spike_ratio:.2f}"))
            continue

        if row.rsi >= config.exit_rsi:
            signals.append(
                Signal(
                    symbol=row.symbol,
                    timeframe=row.timeframe,
                    open_time_ms=row.open_time_ms,
                    action="EXIT_CANDIDATE",
                    confidence=0.65,
                    reason=f"RSI hot at {row.rsi:.2f}; protect profit / avoid late entry",
                )
            )
            continue

        if row.ema_fast < row.ema_slow and regime.trend == "trending_down":
            signals.append(
                Signal(
                    symbol=row.symbol,
                    timeframe=row.timeframe,
                    open_time_ms=row.open_time_ms,
                    action="EXIT_CANDIDATE",
                    confidence=0.70,
                    reason="EMA fast below EMA slow in downtrend regime",
                )
            )
            continue

        if (
            regime.regime in config.buy_regimes
            and row.ema_fast > row.ema_slow
            and config.min_buy_rsi <= row.rsi <= config.max_buy_rsi
        ):
            confidence = _buy_confidence(row)
            signals.append(
                Signal(
                    symbol=row.symbol,
                    timeframe=row.timeframe,
                    open_time_ms=row.open_time_ms,
                    action="BUY_CANDIDATE",
                    confidence=confidence,
                    reason=(
                        f"Trend up with EMA fast > slow, RSI={row.rsi:.2f}, "
                        f"volume_ratio={row.volume_spike_ratio or 0:.2f}"
                    ),
                )
            )
            continue

        signals.append(
            _skip(
                row,
                (
                    f"no conservative setup: regime={regime.regime}, "
                    f"rsi={row.rsi:.2f}, ema_fast={row.ema_fast:.8f}, ema_slow={row.ema_slow:.8f}"
                ),
            )
        )

    return signals


def _missing_feature_reason(row: FeatureRow) -> str | None:
    missing = []
    if row.ema_fast is None:
        missing.append("ema_fast")
    if row.ema_slow is None:
        missing.append("ema_slow")
    if row.rsi is None:
        missing.append("rsi")
    if row.atr is None:
        missing.append("atr")
    if row.volume_sma is None:
        missing.append("volume_sma")
    if missing:
        return "missing warmup features: " + ",".join(missing)
    return None


def _skip(row: FeatureRow, reason: str) -> Signal:
    return Signal(
        symbol=row.symbol,
        timeframe=row.timeframe,
        open_time_ms=row.open_time_ms,
        action="SKIP",
        confidence=0.0,
        reason=reason,
    )


def _buy_confidence(row: FeatureRow) -> float:
    assert row.ema_fast is not None
    assert row.ema_slow is not None
    ema_gap_pct = ((row.ema_fast - row.ema_slow) / row.ema_slow) * 100 if row.ema_slow else 0
    volume_component = min(0.25, ((row.volume_spike_ratio or 1.0) - 0.8) * 0.2)
    trend_component = min(0.45, max(0.0, ema_gap_pct) / 2)
    rsi_component = 0.20 if row.rsi is not None and 50 <= row.rsi <= 65 else 0.10
    return round(min(0.90, 0.20 + trend_component + volume_component + rsi_component), 4)
