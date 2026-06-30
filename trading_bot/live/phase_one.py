from __future__ import annotations

from dataclasses import dataclass

from trading_bot.readiness import ReadinessReport


@dataclass(frozen=True)
class LivePhaseOneConfig:
    capital_idr: float = 1_000_000.0
    max_risk_per_trade_pct: float = 0.25
    daily_max_loss_pct: float = 1.0
    monthly_max_drawdown_pct: float = 5.0
    max_open_positions: int = 1


@dataclass(frozen=True)
class LivePhaseOnePlan:
    status: str
    capital_idr: float
    max_risk_per_trade_idr: float
    daily_max_loss_idr: float
    monthly_max_drawdown_idr: float
    max_open_positions: int
    reason: str


def build_live_phase_one_plan(
    readiness: ReadinessReport,
    config: LivePhaseOneConfig | None = None,
) -> LivePhaseOnePlan:
    if config is None:
        config = LivePhaseOneConfig()
    _validate_config(config)

    max_risk = config.capital_idr * (config.max_risk_per_trade_pct / 100)
    daily_loss = config.capital_idr * (config.daily_max_loss_pct / 100)
    monthly_drawdown = config.capital_idr * (config.monthly_max_drawdown_pct / 100)

    if readiness.status != "READY_FOR_MANUAL_REVIEW":
        return LivePhaseOnePlan(
            status="BLOCKED",
            capital_idr=config.capital_idr,
            max_risk_per_trade_idr=max_risk,
            daily_max_loss_idr=daily_loss,
            monthly_max_drawdown_idr=monthly_drawdown,
            max_open_positions=config.max_open_positions,
            reason="live phase 1 blocked until readiness gate passes",
        )

    return LivePhaseOnePlan(
        status="READY_FOR_OWNER_APPROVAL",
        capital_idr=config.capital_idr,
        max_risk_per_trade_idr=max_risk,
        daily_max_loss_idr=daily_loss,
        monthly_max_drawdown_idr=monthly_drawdown,
        max_open_positions=config.max_open_positions,
        reason="readiness passed; owner approval and exchange sandbox drill still required before any live key",
    )


def _validate_config(config: LivePhaseOneConfig) -> None:
    if config.capital_idr <= 0:
        raise ValueError("capital_idr must be positive")
    if config.max_risk_per_trade_pct <= 0 or config.max_risk_per_trade_pct > 0.25:
        raise ValueError("max_risk_per_trade_pct must be > 0 and <= 0.25 for phase 1")
    if config.daily_max_loss_pct <= 0 or config.daily_max_loss_pct > 1.0:
        raise ValueError("daily_max_loss_pct must be > 0 and <= 1.0")
    if config.monthly_max_drawdown_pct <= 0 or config.monthly_max_drawdown_pct > 5.0:
        raise ValueError("monthly_max_drawdown_pct must be > 0 and <= 5.0")
    if config.max_open_positions != 1:
        raise ValueError("phase 1 requires max_open_positions=1")
