from pathlib import Path
import unittest

from trading_bot.config import BotConfig, ConfigError, load_config, validate_config


class ConfigGuardTest(unittest.TestCase):
    def test_sample_config_is_safe(self) -> None:
        config = load_config(Path("config/bot.sample.toml"))

        self.assertEqual(config.mode, "research")
        self.assertFalse(config.live_enabled)
        self.assertEqual(config.symbols, ("BTC/USDT", "ETH/USDT"))

    def test_live_requires_manual_approval(self) -> None:
        config = BotConfig(
            mode="paper",
            live_enabled=True,
            approved_live=False,
            symbols=("BTC/USDT",),
            market_type="crypto_spot",
            timeframes=("15m",),
            data_root="work/market_data",
            data_provider="binance_public",
            max_open_positions=1,
            daily_max_loss_pct=1.0,
            monthly_max_drawdown_pct=5.0,
            entry_windows_wib=("08:00-11:00",),
            always_collect_data=True,
        )

        with self.assertRaises(ConfigError):
            validate_config(config)

    def test_unknown_symbol_is_rejected(self) -> None:
        config = BotConfig(
            mode="research",
            live_enabled=False,
            approved_live=False,
            symbols=("DOGE/USDT",),
            market_type="crypto_spot",
            timeframes=("15m",),
            data_root="work/market_data",
            data_provider="binance_public",
            max_open_positions=1,
            daily_max_loss_pct=1.0,
            monthly_max_drawdown_pct=5.0,
            entry_windows_wib=("08:00-11:00",),
            always_collect_data=True,
        )

        with self.assertRaises(ConfigError):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()
