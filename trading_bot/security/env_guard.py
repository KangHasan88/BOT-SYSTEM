from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class EnvSecurityReport:
    ok: bool
    errors: list[str]
    warnings: list[str]


def load_env_file(path: str | Path) -> dict[str, str]:
    env: dict[str, str] = {}
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"env file not found: {file_path}")
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def validate_env_security(env: Mapping[str, str]) -> EnvSecurityReport:
    errors: list[str] = []
    warnings: list[str] = []

    live_enabled = _bool(env.get("BOT_LIVE_ENABLED", "false"))
    approved_live = _bool(env.get("BOT_APPROVED_LIVE", "false"))
    withdrawal_permission = _bool(env.get("API_WITHDRAWAL_PERMISSION", "false"))
    api_key = env.get("EXCHANGE_API_KEY", "")
    api_secret = env.get("EXCHANGE_API_SECRET", "")

    if withdrawal_permission:
        errors.append("API_WITHDRAWAL_PERMISSION must be false")
    if live_enabled and not approved_live:
        errors.append("BOT_LIVE_ENABLED requires BOT_APPROVED_LIVE=true")
    if live_enabled:
        errors.append("live execution is not allowed by v1 security guard")
    if bool(api_key) != bool(api_secret):
        errors.append("EXCHANGE_API_KEY and EXCHANGE_API_SECRET must be provided together")
    if api_key or api_secret:
        warnings.append("private exchange credentials detected; verify trading-only permission and IP whitelist")
    if env.get("BOT_MODE") == "live":
        errors.append("BOT_MODE=live is blocked until production go/no-go checklist passes")

    return EnvSecurityReport(ok=not errors, errors=errors, warnings=warnings)


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
