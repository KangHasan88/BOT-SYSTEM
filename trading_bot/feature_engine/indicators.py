from __future__ import annotations


def ema(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    if not values:
        return []

    alpha = 2 / (period + 1)
    result: list[float | None] = []
    current: float | None = None

    for index, value in enumerate(values):
        if index + 1 < period:
            result.append(None)
            continue
        if index + 1 == period:
            current = sum(values[:period]) / period
        else:
            assert current is not None
            current = (value * alpha) + (current * (1 - alpha))
        result.append(current)

    return result


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) <= period:
        return [None for _ in values]

    result: list[float | None] = [None for _ in values]
    gains: list[float] = []
    losses: list[float] = []

    for index in range(1, period + 1):
        delta = values[index] - values[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    result[period] = _rsi_from_averages(avg_gain, avg_loss)

    for index in range(period + 1, len(values)):
        delta = values[index] - values[index - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        result[index] = _rsi_from_averages(avg_gain, avg_loss)

    return result


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows, and closes must have the same length")
    if not highs:
        return []

    true_ranges: list[float] = []
    for index in range(len(highs)):
        if index == 0:
            true_ranges.append(highs[index] - lows[index])
        else:
            true_ranges.append(
                max(
                    highs[index] - lows[index],
                    abs(highs[index] - closes[index - 1]),
                    abs(lows[index] - closes[index - 1]),
                )
            )

    result: list[float | None] = [None for _ in true_ranges]
    if len(true_ranges) < period:
        return result

    current = sum(true_ranges[:period]) / period
    result[period - 1] = current

    for index in range(period, len(true_ranges)):
        current = ((current * (period - 1)) + true_ranges[index]) / period
        result[index] = current

    return result


def sma(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")

    result: list[float | None] = []
    window_sum = 0.0
    for index, value in enumerate(values):
        window_sum += value
        if index >= period:
            window_sum -= values[index - period]
        if index + 1 < period:
            result.append(None)
        else:
            result.append(window_sum / period)
    return result


def _rsi_from_averages(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
