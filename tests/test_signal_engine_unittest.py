from pathlib import Path
import tempfile
import unittest

from trading_bot.feature_engine.features import FeatureRow
from trading_bot.feature_engine.regime import RegimeRow
from trading_bot.strategy import SignalCsvStore, generate_conservative_signals


def feature(
    open_time_ms: int = 1,
    ema_fast: float | None = 105.0,
    ema_slow: float | None = 100.0,
    rsi: float | None = 58.0,
    volume_ratio: float | None = 1.0,
) -> FeatureRow:
    return FeatureRow(
        symbol="BTC/USDT",
        timeframe="15m",
        open_time_ms=open_time_ms,
        close=106.0,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        rsi=rsi,
        atr=1.0,
        volume_sma=100.0,
        body_pct=0.5,
        upper_wick_pct=0.2,
        lower_wick_pct=0.2,
        range_pct=1.0,
        volume_spike_ratio=volume_ratio,
    )


def regime(open_time_ms: int = 1, regime_name: str = "trending_up", trend: str = "trending_up") -> RegimeRow:
    return RegimeRow(
        symbol="BTC/USDT",
        timeframe="15m",
        open_time_ms=open_time_ms,
        regime=regime_name,
        trend=trend,
        volatility="normal_volatility",
        liquidity="normal_liquidity",
        reason="test",
    )


class SignalEngineTest(unittest.TestCase):
    def test_buy_candidate_in_clean_uptrend(self) -> None:
        signals = generate_conservative_signals([feature()], [regime()])

        self.assertEqual(signals[0].action, "BUY_CANDIDATE")
        self.assertGreater(signals[0].confidence, 0)

    def test_skip_when_features_are_missing(self) -> None:
        signals = generate_conservative_signals([feature(ema_fast=None)], [regime()])

        self.assertEqual(signals[0].action, "SKIP")
        self.assertIn("missing warmup", signals[0].reason)

    def test_skip_unsafe_regime(self) -> None:
        signals = generate_conservative_signals(
            [feature()],
            [regime(regime_name="volatile", trend="trending_up")],
        )

        self.assertEqual(signals[0].action, "SKIP")
        self.assertIn("unsafe regime", signals[0].reason)

    def test_exit_when_rsi_hot(self) -> None:
        signals = generate_conservative_signals([feature(rsi=80.0)], [regime()])

        self.assertEqual(signals[0].action, "EXIT_CANDIDATE")
        self.assertIn("RSI hot", signals[0].reason)

    def test_exit_when_downtrend(self) -> None:
        signals = generate_conservative_signals(
            [feature(ema_fast=95.0, ema_slow=100.0, rsi=55.0)],
            [regime(regime_name="trending_down", trend="trending_down")],
        )

        self.assertEqual(signals[0].action, "EXIT_CANDIDATE")

    def test_signal_csv_export(self) -> None:
        signals = generate_conservative_signals([feature()], [regime()])

        with tempfile.TemporaryDirectory() as temp_dir:
            path = SignalCsvStore(Path(temp_dir)).write(signals, "BTC/USDT", "15m")

            self.assertTrue(path.exists())
            self.assertIn("action", path.read_text(encoding="utf-8").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
