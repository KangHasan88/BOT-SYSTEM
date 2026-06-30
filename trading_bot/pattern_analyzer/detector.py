from __future__ import annotations

from trading_bot.data_collector.models import Candle
from trading_bot.pattern_analyzer.patterns import PatternSignal, SwingPoint


def detect_swing_points(candles: list[Candle], left: int = 2, right: int = 2) -> list[SwingPoint]:
    if left < 1 or right < 1:
        raise ValueError("left and right must be positive")

    ordered = sorted(candles, key=lambda candle: candle.open_time_ms)
    swings: list[SwingPoint] = []

    for index in range(left, len(ordered) - right):
        current = ordered[index]
        window = ordered[index - left : index + right + 1]
        other_highs = [candle.high for offset, candle in enumerate(window) if offset != left]
        other_lows = [candle.low for offset, candle in enumerate(window) if offset != left]

        if current.high > max(other_highs):
            swings.append(
                SwingPoint(
                    symbol=current.symbol,
                    timeframe=current.timeframe,
                    open_time_ms=current.open_time_ms,
                    kind="swing_high",
                    price=current.high,
                )
            )

        if current.low < min(other_lows):
            swings.append(
                SwingPoint(
                    symbol=current.symbol,
                    timeframe=current.timeframe,
                    open_time_ms=current.open_time_ms,
                    kind="swing_low",
                    price=current.low,
                )
            )

    return swings


def detect_price_action_patterns(
    candles: list[Candle],
    lookback: int = 20,
    min_sweep_pct: float = 0.05,
    volume_spike_ratio: float = 1.5,
) -> list[PatternSignal]:
    ordered = sorted(candles, key=lambda candle: candle.open_time_ms)
    if len(ordered) < lookback + 1:
        return []

    signals: list[PatternSignal] = []
    for index in range(lookback, len(ordered)):
        current = ordered[index]
        history = ordered[index - lookback : index]
        recent_high = max(candle.high for candle in history)
        recent_low = min(candle.low for candle in history)
        avg_volume = sum(candle.volume for candle in history) / len(history)
        volume_ratio = current.volume / avg_volume if avg_volume else 0.0
        upper_sweep_pct = ((current.high - recent_high) / recent_high) * 100
        lower_sweep_pct = ((recent_low - current.low) / recent_low) * 100

        if current.high > recent_high and current.close < recent_high and upper_sweep_pct >= min_sweep_pct:
            signals.append(
                PatternSignal(
                    symbol=current.symbol,
                    timeframe=current.timeframe,
                    open_time_ms=current.open_time_ms,
                    pattern="sweep_up",
                    score=_score(upper_sweep_pct, volume_ratio),
                    reference_price=recent_high,
                    reason=(
                        f"High swept lookback high {recent_high:.8f} by {upper_sweep_pct:.4f}% "
                        f"then closed back below it; volume_ratio={volume_ratio:.2f}"
                    ),
                )
            )

        if current.low < recent_low and current.close > recent_low and lower_sweep_pct >= min_sweep_pct:
            signals.append(
                PatternSignal(
                    symbol=current.symbol,
                    timeframe=current.timeframe,
                    open_time_ms=current.open_time_ms,
                    pattern="sweep_down",
                    score=_score(lower_sweep_pct, volume_ratio),
                    reference_price=recent_low,
                    reason=(
                        f"Low swept lookback low {recent_low:.8f} by {lower_sweep_pct:.4f}% "
                        f"then closed back above it; volume_ratio={volume_ratio:.2f}"
                    ),
                )
            )

        if current.high > recent_high and current.close < current.open and volume_ratio >= volume_spike_ratio:
            signals.append(
                PatternSignal(
                    symbol=current.symbol,
                    timeframe=current.timeframe,
                    open_time_ms=current.open_time_ms,
                    pattern="false_breakout_up",
                    score=_score(max(upper_sweep_pct, 0.0), volume_ratio),
                    reference_price=recent_high,
                    reason=(
                        f"Break above lookback high failed with bearish close; "
                        f"volume_ratio={volume_ratio:.2f}"
                    ),
                )
            )

        if current.low < recent_low and current.close > current.open and volume_ratio >= volume_spike_ratio:
            signals.append(
                PatternSignal(
                    symbol=current.symbol,
                    timeframe=current.timeframe,
                    open_time_ms=current.open_time_ms,
                    pattern="false_breakout_down",
                    score=_score(max(lower_sweep_pct, 0.0), volume_ratio),
                    reference_price=recent_low,
                    reason=(
                        f"Break below lookback low failed with bullish close; "
                        f"volume_ratio={volume_ratio:.2f}"
                    ),
                )
            )

        if volume_ratio >= volume_spike_ratio and _body_pct(current) <= 0.25:
            signals.append(
                PatternSignal(
                    symbol=current.symbol,
                    timeframe=current.timeframe,
                    open_time_ms=current.open_time_ms,
                    pattern="absorption_candidate",
                    score=min(1.0, volume_ratio / 4),
                    reference_price=current.close,
                    reason=(
                        f"High volume with small body; body_pct_of_range={_body_pct(current):.2f}, "
                        f"volume_ratio={volume_ratio:.2f}"
                    ),
                )
            )

    return signals


def _score(sweep_pct: float, volume_ratio: float) -> float:
    sweep_component = min(0.6, sweep_pct / 1.0)
    volume_component = min(0.4, volume_ratio / 5)
    return round(sweep_component + volume_component, 4)


def _body_pct(candle: Candle) -> float:
    candle_range = candle.high - candle.low
    if candle_range <= 0:
        return 0.0
    return abs(candle.close - candle.open) / candle_range
