from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import load_config


@dataclass(frozen=True)
class ProductionSmokeCheck:
    name: str
    status: str
    reason: str


@dataclass(frozen=True)
class ProductionSmokeReport:
    status: str
    checks: list[ProductionSmokeCheck]
    generated_at_utc: str


def evaluate_production_smoke(
    config_path: str | Path = "config/bot.sample.toml",
    smoke_path: str | Path = "deploy/smoke-vps.sh",
    runbook_path: str | Path = "docs/vps-deployment.md",
) -> ProductionSmokeReport:
    config = load_config(Path(config_path))
    root = Path(config.data_root)
    smoke = Path(smoke_path).read_text(encoding="utf-8")
    runbook = Path(runbook_path).read_text(encoding="utf-8")
    checks = [
        _check(
            "config_live_disabled",
            not config.live_enabled and config.mode in {"research", "paper"},
            "config is non-live",
            "config must stay non-live for production smoke",
        ),
        _check(
            "smoke_script_commands",
            all(command in smoke for command in ["validate-config", "run-cycle", "build-dashboard"]),
            "smoke script covers config, cycle, dashboard",
            "smoke script must cover config, cycle, dashboard",
        ),
        _check(
            "rollback_timer_disable",
            "systemctl disable --now trading-bot-cycle.timer" in runbook
            and "systemctl stop trading-bot-cycle.service" in runbook,
            "rollback disables timer and stops service",
            "rollback must disable timer and stop service",
        ),
        _check(
            "rollback_restore_steps",
            "bot.toml.bak" in runbook and "data.bak" in runbook and "journalctl" in runbook,
            "rollback restores config/data and preserves logs",
            "rollback must restore config/data and preserve logs",
        ),
        _report_status_check(root, "qa/security/report.json", "PASSED", "security_qa"),
        _report_status_check(root, "qa/risk_guard_drill/report.json", "PASSED", "risk_guard_drill"),
        _report_status_check(root, "qa/vps_readiness/report.json", "PASSED", "vps_readiness"),
        _report_status_check(root, "qa/incident_drill/report.json", "PASSED", "incident_drill"),
        _go_no_go_check(root),
    ]
    return ProductionSmokeReport(
        status="PASSED" if all(check.status == "PASSED" for check in checks) else "BLOCKED",
        checks=checks,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def save_production_smoke_report(report: ProductionSmokeReport, root: str | Path) -> Path:
    path = Path(root) / "qa" / "production_smoke" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _report_status_check(root: Path, relative_path: str, expected: str, name: str) -> ProductionSmokeCheck:
    payload = _read_json(root / relative_path)
    if payload is None:
        return ProductionSmokeCheck(name, "FAILED", f"missing report: {relative_path}")
    status = str(payload.get("status", ""))
    if status == expected:
        return ProductionSmokeCheck(name, "PASSED", f"report status={status}")
    return ProductionSmokeCheck(name, "FAILED", f"report status={status or 'unknown'}")


def _go_no_go_check(root: Path) -> ProductionSmokeCheck:
    payload = _read_json(root / "qa" / "live_go_no_go" / "report.json")
    if payload is None:
        return ProductionSmokeCheck("live_go_no_go", "FAILED", "missing live go/no-go report")
    decision = str(payload.get("decision", ""))
    if decision in {"NO_GO", "GO_FOR_OWNER_REVIEW"}:
        return ProductionSmokeCheck("live_go_no_go", "PASSED", f"decision={decision}")
    return ProductionSmokeCheck("live_go_no_go", "FAILED", f"decision={decision or 'unknown'}")


def _check(name: str, passed: bool, passed_reason: str, failed_reason: str) -> ProductionSmokeCheck:
    return ProductionSmokeCheck(
        name=name,
        status="PASSED" if passed else "FAILED",
        reason=passed_reason if passed else failed_reason,
    )


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
