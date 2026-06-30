from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.data_collector.market_context import SymbolMetadata
from trading_bot.risk_manager import (
    AccountState,
    TradeCandidate,
    evaluate_daily_profit_lock,
    evaluate_position_lock,
    evaluate_trade_risk,
)
from trading_bot.risk_manager.models import RiskConfig
from trading_bot.safety import activate_kill_switch, clear_kill_switch, read_kill_switch


@dataclass(frozen=True)
class RiskGuardCheck:
    name: str
    status: str
    expected: str
    actual: str
    reason: str


@dataclass(frozen=True)
class RiskGuardDrillReport:
    status: str
    generated_at_utc: str
    checks: list[RiskGuardCheck]


def run_risk_guard_drill(root: str | Path, symbol: str = "BTC/USDT") -> RiskGuardDrillReport:
    metadata = SymbolMetadata(
        symbol=symbol,
        base_asset=symbol.split("/")[0],
        quote_asset=symbol.split("/")[1],
        min_notional=1.0,
        price_precision=8,
        quantity_precision=8,
        taker_fee_pct=0.10,
        maker_fee_pct=0.10,
        source="risk_guard_drill",
    )
    checks = [
        _daily_stop_check(metadata),
        _monthly_drawdown_check(metadata),
        _profit_floor_check(),
        _daily_target_check(),
        _position_lock_check(),
        _kill_switch_check(Path(root)),
    ]
    return RiskGuardDrillReport(
        status="PASSED" if all(check.status == "PASSED" for check in checks) else "FAILED",
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        checks=checks,
    )


def save_risk_guard_drill_report(report: RiskGuardDrillReport, root: str | Path) -> Path:
    path = Path(root) / "qa" / "risk_guard_drill" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _daily_stop_check(metadata: SymbolMetadata) -> RiskGuardCheck:
    decision = evaluate_trade_risk(
        AccountState(
            equity=990.0,
            day_start_equity=1_000.0,
            month_start_equity=1_000.0,
            open_positions=0,
        ),
        _candidate(metadata.symbol),
        metadata,
        RiskConfig(daily_max_loss_pct=1.0),
    )
    passed = decision.status == "REJECTED" and "daily max loss reached" in decision.reason
    return _check(
        "daily_stop",
        passed,
        "REJECTED daily max loss reached",
        f"{decision.status} {decision.reason}",
        decision.reason,
    )


def _monthly_drawdown_check(metadata: SymbolMetadata) -> RiskGuardCheck:
    decision = evaluate_trade_risk(
        AccountState(
            equity=949.0,
            day_start_equity=1_000.0,
            month_start_equity=1_000.0,
            open_positions=0,
        ),
        _candidate(metadata.symbol),
        metadata,
        RiskConfig(daily_max_loss_pct=10.0, monthly_max_drawdown_pct=5.0),
    )
    passed = decision.status == "REJECTED" and "monthly max drawdown reached" in decision.reason
    return _check(
        "monthly_drawdown",
        passed,
        "REJECTED monthly max drawdown reached",
        f"{decision.status} {decision.reason}",
        decision.reason,
    )


def _profit_floor_check() -> RiskGuardCheck:
    state = evaluate_daily_profit_lock(
        day_start_equity=1_000.0,
        current_equity=1_003.0,
        previous_high_watermark_equity=1_010.0,
    )
    passed = state.status == "STOP_TRADING"
    return _check(
        "profit_floor_stop",
        passed,
        "STOP_TRADING",
        state.status,
        state.reason,
    )


def _daily_target_check() -> RiskGuardCheck:
    state = evaluate_daily_profit_lock(day_start_equity=1_000.0, current_equity=1_011.0)
    passed = state.status == "DAILY_TARGET_HIT"
    return _check(
        "daily_target_stop",
        passed,
        "DAILY_TARGET_HIT",
        state.status,
        state.reason,
    )


def _position_lock_check() -> RiskGuardCheck:
    decision = evaluate_position_lock("buy", entry_price=100.0, stop_price=98.0, current_price=103.0)
    passed = decision.should_update_stop and decision.new_stop_price > 100.0
    return _check(
        "position_profit_lock",
        passed,
        "stop moved above entry",
        f"should_update={decision.should_update_stop}, stop={decision.new_stop_price:.8f}",
        decision.reason,
    )


def _kill_switch_check(root: Path) -> RiskGuardCheck:
    sandbox_root = root / "qa" / "risk_guard_drill" / "kill_switch_sandbox"
    activate_kill_switch(sandbox_root, "risk guard drill")
    active = read_kill_switch(sandbox_root)
    clear_kill_switch(sandbox_root)
    cleared = read_kill_switch(sandbox_root)
    passed = active.active and not cleared.active
    return _check(
        "kill_switch_roundtrip",
        passed,
        "active then cleared",
        f"active={str(active.active).lower()}, cleared_active={str(cleared.active).lower()}",
        active.reason,
    )


def _candidate(symbol: str) -> TradeCandidate:
    return TradeCandidate(symbol=symbol, side="buy", entry_price=100.0, stop_price=99.0, confidence=0.8)


def _check(name: str, passed: bool, expected: str, actual: str, reason: str) -> RiskGuardCheck:
    return RiskGuardCheck(
        name=name,
        status="PASSED" if passed else "FAILED",
        expected=expected,
        actual=actual,
        reason=reason,
    )
