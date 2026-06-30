from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class KillSwitchState:
    active: bool
    reason: str
    created_at_utc: str | None


def activate_kill_switch(root: str | Path, reason: str) -> Path:
    if not reason.strip():
        raise ValueError("kill switch reason is required")
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = KillSwitchState(
        active=True,
        reason=reason.strip(),
        created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    path.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
    return path


def clear_kill_switch(root: str | Path) -> None:
    path = _path(root)
    if path.exists():
        path.unlink()


def read_kill_switch(root: str | Path) -> KillSwitchState:
    path = _path(root)
    if not path.exists():
        return KillSwitchState(False, "", None)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return KillSwitchState(
        active=bool(payload.get("active", False)),
        reason=str(payload.get("reason", "")),
        created_at_utc=payload.get("created_at_utc"),
    )


def _path(root: str | Path) -> Path:
    return Path(root) / "safety" / "kill_switch.json"
