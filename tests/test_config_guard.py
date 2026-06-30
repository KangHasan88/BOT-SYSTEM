from pathlib import Path

import pytest

from trading_bot.config import ConfigError, load_config, validate_config, BotConfig


def test_sample_config_is_safe() -> None:
    config = load_config(Path("config/bot.sample.toml"))

    assert config.mode == "research"
    assert config.live_enabled is False
    assert config.symbols == ("BTC/USDT", "ETH/USDT")


def test_live_requires_manual_approval() -> None:
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

    with pytest.raises(ConfigError):
        validate_config(config)


def test_unknown_symbol_is_rejected() -> None:
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

    with pytest.raises(ConfigError):
        validate_config(config)
