from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.security import SecretFinding, load_env_file, scan_for_secrets, validate_env_security


@dataclass(frozen=True)
class SecurityQaCheck:
    name: str
    status: str
    reason: str


@dataclass(frozen=True)
class SecurityQaReport:
    status: str
    env_file: str
    scan_root: str
    checks: list[SecurityQaCheck]
    secret_findings: list[SecretFinding]
    warnings: list[str] = field(default_factory=list)
    generated_at_utc: str = ""


def generate_security_qa_report(env_file: str | Path, scan_root: str | Path) -> SecurityQaReport:
    env = load_env_file(env_file)
    env_report = validate_env_security(env)
    findings = scan_for_secrets(scan_root)
    checks = [
        SecurityQaCheck(
            name="env_security",
            status="PASSED" if env_report.ok else "FAILED",
            reason="; ".join(env_report.errors) if env_report.errors else "env guard passed",
        ),
        SecurityQaCheck(
            name="withdrawal_disabled",
            status="PASSED" if _is_false(env.get("API_WITHDRAWAL_PERMISSION", "false")) else "FAILED",
            reason="API_WITHDRAWAL_PERMISSION is false"
            if _is_false(env.get("API_WITHDRAWAL_PERMISSION", "false"))
            else "API_WITHDRAWAL_PERMISSION must be false",
        ),
        SecurityQaCheck(
            name="live_blocked",
            status="PASSED"
            if _is_false(env.get("BOT_LIVE_ENABLED", "false")) and env.get("BOT_MODE", "") != "live"
            else "FAILED",
            reason="live execution is disabled"
            if _is_false(env.get("BOT_LIVE_ENABLED", "false")) and env.get("BOT_MODE", "") != "live"
            else "live execution must remain disabled",
        ),
        SecurityQaCheck(
            name="credential_pairing",
            status="PASSED" if bool(env.get("EXCHANGE_API_KEY")) == bool(env.get("EXCHANGE_API_SECRET")) else "FAILED",
            reason="key/secret pairing is valid"
            if bool(env.get("EXCHANGE_API_KEY")) == bool(env.get("EXCHANGE_API_SECRET"))
            else "EXCHANGE_API_KEY and EXCHANGE_API_SECRET must be provided together",
        ),
        SecurityQaCheck(
            name="secret_scan",
            status="PASSED" if not findings else "FAILED",
            reason=f"secret findings={len(findings)}",
        ),
    ]
    return SecurityQaReport(
        status="PASSED" if all(check.status == "PASSED" for check in checks) else "BLOCKED",
        env_file=str(env_file),
        scan_root=str(scan_root),
        checks=checks,
        secret_findings=findings,
        warnings=env_report.warnings,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def save_security_qa_report(report: SecurityQaReport, root: str | Path) -> Path:
    path = Path(root) / "qa" / "security" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _is_false(value: str) -> bool:
    return value.strip().lower() in {"", "0", "false", "no", "off"}
