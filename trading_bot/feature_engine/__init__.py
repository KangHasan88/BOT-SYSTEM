"""Market feature computation package."""

from trading_bot.feature_engine.csv_store import FeatureCsvStore
from trading_bot.feature_engine.features import FeatureConfig, FeatureRow, build_features
from trading_bot.feature_engine.indicators import atr, ema, rsi, sma
from trading_bot.feature_engine.regime import RegimeConfig, RegimeRow, classify_regimes
from trading_bot.feature_engine.regime_store import RegimeCsvStore

__all__ = [
    "FeatureConfig",
    "FeatureCsvStore",
    "FeatureRow",
    "RegimeConfig",
    "RegimeCsvStore",
    "RegimeRow",
    "atr",
    "build_features",
    "classify_regimes",
    "ema",
    "rsi",
    "sma",
]
