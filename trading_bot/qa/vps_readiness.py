from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import load_config


@dataclass(frozen=True)
class VpsReadinessCheck:
    name: str
    status: str
    reason: str


@dataclass(frozen=True)
class VpsReadinessReport:
    status: str
    checks: list[VpsReadinessCheck]
    generated_at_utc: str


def evaluate_vps_readiness(
    config_path: str | Path = "config/bot.vps.sample.toml",
    service_path: str | Path = "deploy/systemd/trading-bot-cycle.service",
    timer_path: str | Path = "deploy/systemd/trading-bot-cycle.timer",
    smoke_path: str | Path = "deploy/smoke-vps.sh",
) -> VpsReadinessReport:
    config = load_config(Path(config_path))
    service = Path(service_path).read_text(encoding="utf-8")
    timer = Path(timer_path).read_text(encoding="utf-8")
    smoke = Path(smoke_path).read_text(encoding="utf-8")

    checks = [
        _check(
            "config_paper_only",
            config.mode == "paper" and not config.live_enabled and not config.approved_live,
            "VPS config is paper-only and live disabled",
            "VPS config must stay paper-only with live disabled",
        ),
        _check(
            "config_data_root",
            config.data_root == "/var/lib/trading-bot/data",
            "VPS data root points to /var/lib/trading-bot/data",
            f"unexpected data_root={config.data_root}",
        ),
        _check(
            "service_user",
            "User=tradingbot" in service and "Group=tradingbot" in service,
            "systemd service runs as tradingbot",
            "systemd service must run as tradingbot user/group",
        ),
        _check(
            "service_hardening",
            all(
                token in service
                for token in [
                    "NoNewPrivileges=true",
                    "PrivateTmp=true",
                    "ProtectSystem=strict",
                    "ProtectHome=true",
                    "ReadWritePaths=/var/lib/trading-bot /var/log/trading-bot",
                ]
            ),
            "systemd hardening options are present",
            "missing one or more systemd hardening options",
        ),
        _check(
            "service_command",
            "run-cycle" in service and "--sync-latest" in service and "live" not in service.lower(),
            "service runs research cycle with sync and no live command",
            "service command must run-cycle with sync and must not mention live",
        ),
        _check(
            "timer_restart_behavior",
            "OnBootSec=2min" in timer and "OnUnitActiveSec=15min" in timer and "Persistent=true" in timer,
            "timer starts after boot, repeats every 15 minutes, and catches missed runs",
            "timer must define boot delay, 15 minute cadence, and Persistent=true",
        ),
        _check(
            "smoke_script",
            all(command in smoke for command in ["validate-config", "run-cycle", "build-dashboard"]),
            "smoke script validates config, cycle, and dashboard",
            "smoke script must validate config, run cycle, and build dashboard",
        ),
        _check(
            "monitoring_commands",
            "journalctl -u trading-bot-cycle.service" in _read_text("docs/vps-deployment.md")
            and "systemctl status trading-bot-cycle.timer" in _read_text("docs/vps-deployment.md"),
            "runbook includes systemctl and journalctl monitoring commands",
            "runbook must include timer status and journal log commands",
        ),
    ]
    return VpsReadinessReport(
        status="PASSED" if all(check.status == "PASSED" for check in checks) else "BLOCKED",
        checks=checks,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def save_vps_readiness_report(report: VpsReadinessReport, root: str | Path) -> Path:
    path = Path(root) / "qa" / "vps_readiness" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _check(name: str, passed: bool, passed_reason: str, failed_reason: str) -> VpsReadinessCheck:
    return VpsReadinessCheck(
        name=name,
        status="PASSED" if passed else "FAILED",
        reason=passed_reason if passed else failed_reason,
    )


def _read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
