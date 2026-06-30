from __future__ import annotations

from dataclasses import dataclass

from trading_bot.feature_engine.features import FeatureRow


@dataclass(frozen=True)
class RegimeRow:
    symbol: str
    timeframe: str
    open_time_ms: int
    regime: str
    trend: str
    volatility: str
    liquidity: str
    reason: str


@dataclass(frozen=True)
class RegimeConfig:
    slope_lookback: int = 5
    min_trend_slope_pct: float = 0.15
    min_ema_gap_pct: float = 0.10
    high_volatility_range_pct: float = 2.0
    low_volatility_range_pct: float = 0.35
    low_liquidity_volume_ratio: float = 0.50


def classify_regimes(
    rows: list[FeatureRow],
    config: RegimeConfig | None = None,
) -> list[RegimeRow]:
    if config is None:
        config = RegimeConfig()
    if config.slope_lookback < 1:
        raise ValueError("slope_lookback must be >= 1")

    output: list[RegimeRow] = []
    for index, row in enumerate(rows):
        trend = "unknown"
        volatility = _volatility_label(row, config)
        liquidity = _liquidity_label(row, config)
        reasons: list[str] = []

        if row.ema_fast is not None and row.ema_slow is not None and index >= config.slope_lookback:
            previous = rows[index - config.slope_lookback]
            if previous.ema_slow is not None and previous.ema_slow != 0:
                slope_pct = ((row.ema_slow - previous.ema_slow) / previous.ema_slow) * 100
                ema_gap_pct = ((row.ema_fast - row.ema_slow) / row.ema_slow) * 100
                reasons.append(f"slope_pct={slope_pct:.4f}")
                reasons.append(f"ema_gap_pct={ema_gap_pct:.4f}")

                if slope_pct >= config.min_trend_slope_pct and ema_gap_pct >= config.min_ema_gap_pct:
                    trend = "trending_up"
                elif slope_pct <= -config.min_trend_slope_pct and ema_gap_pct <= -config.min_ema_gap_pct:
                    trend = "trending_down"
                elif abs(slope_pct) < config.min_trend_slope_pct and row.range_pct <= config.low_volatility_range_pct:
                    trend = "sideways"
                else:
                    trend = "mixed"

        if liquidity == "low_liquidity":
            regime = "low_liquidity"
        elif volatility == "high_volatility":
            regime = "volatile"
        elif trend in {"trending_up", "trending_down", "sideways"}:
            regime = trend
        else:
            regime = "mixed"

        reasons.append(f"range_pct={row.range_pct:.4f}")
        if row.volume_spike_ratio is not None:
            reasons.append(f"volume_ratio={row.volume_spike_ratio:.4f}")

        output.append(
            RegimeRow(
                symbol=row.symbol,
                timeframe=row.timeframe,
                open_time_ms=row.open_time_ms,
                regime=regime,
                trend=trend,
                volatility=volatility,
                liquidity=liquidity,
                reason=", ".join(reasons),
            )
        )

    return output


def _volatility_label(row: FeatureRow, config: RegimeConfig) -> str:
    if row.range_pct >= config.high_volatility_range_pct:
        return "high_volatility"
    if row.range_pct <= config.low_volatility_range_pct:
        return "low_volatility"
    return "normal_volatility"


def _liquidity_label(row: FeatureRow, config: RegimeConfig) -> str:
    if row.volume_spike_ratio is not None and row.volume_spike_ratio <= config.low_liquidity_volume_ratio:
        return "low_liquidity"
    return "normal_liquidity"
