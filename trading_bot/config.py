from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


ALLOWED_SYMBOLS = {"BTC/USDT", "ETH/USDT"}
ALLOWED_MODES = {"research", "backtest", "paper", "live"}


@dataclass(frozen=True)
class BotConfig:
    mode: str
    live_enabled: bool
    approved_live: bool
    symbols: tuple[str, ...]
    market_type: str
    timeframes: tuple[str, ...]
    data_root: str
    data_provider: str
    max_open_positions: int
    daily_max_loss_pct: float
    monthly_max_drawdown_pct: float
    entry_windows_wib: tuple[str, ...]
    always_collect_data: bool


class ConfigError(ValueError):
    """Raised when configuration violates bot safety policy."""


def load_config(path: str | Path) -> BotConfig:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))

    bot = raw.get("bot", {})
    market = raw.get("market", {})
    data = raw.get("data", {})
    risk = raw.get("risk", {})
    sessions = raw.get("sessions", {})

    config = BotConfig(
        mode=str(bot.get("mode", "research")),
        live_enabled=bool(bot.get("live_enabled", False)),
        approved_live=bool(bot.get("approved_live", False)),
        symbols=tuple(market.get("symbols", [])),
        market_type=str(market.get("type", "")),
        timeframes=tuple(market.get("timeframes", [])),
        data_root=str(data.get("root", "work/market_data")),
        data_provider=str(data.get("provider", "binance_public")),
        max_open_positions=int(risk.get("max_open_positions", 1)),
        daily_max_loss_pct=float(risk.get("daily_max_loss_pct", 1.0)),
        monthly_max_drawdown_pct=float(risk.get("monthly_max_drawdown_pct", 5.0)),
        entry_windows_wib=tuple(sessions.get("entry_windows_wib", [])),
        always_collect_data=bool(sessions.get("always_collect_data", True)),
    )
    validate_config(config)
    return config


def validate_config(config: BotConfig) -> None:
    if config.mode not in ALLOWED_MODES:
        raise ConfigError(f"Unsupported mode: {config.mode}")

    unknown_symbols = set(config.symbols) - ALLOWED_SYMBOLS
    if unknown_symbols:
        raise ConfigError(f"Unknown symbols are not allowed in v1: {sorted(unknown_symbols)}")

    if config.market_type != "crypto_spot":
        raise ConfigError("v1 only allows crypto_spot market type")

    allowed_timeframes = {"15m", "1h", "4h"}
    unknown_timeframes = set(config.timeframes) - allowed_timeframes
    if unknown_timeframes:
        raise ConfigError(f"unsupported v1 timeframes: {sorted(unknown_timeframes)}")

    if config.data_provider != "binance_public":
        raise ConfigError("v1 only supports binance_public data provider")

    if config.max_open_positions > 1:
        raise ConfigError("v1 allows max_open_positions <= 1")

    if config.daily_max_loss_pct > 1.0:
        raise ConfigError("daily_max_loss_pct must be <= 1.0 for the conservative profile")

    if config.monthly_max_drawdown_pct > 5.0:
        raise ConfigError("monthly_max_drawdown_pct must be <= 5.0 for the conservative profile")

    if not config.entry_windows_wib:
        raise ConfigError("at least one entry window is required")

    if config.live_enabled and (config.mode != "live" or not config.approved_live):
        raise ConfigError("live_enabled requires mode=live and approved_live=true")
