from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    event: str
    level: str
    message: str
    created_at_utc: str
    context: dict[str, Any] = field(default_factory=dict)


class JsonlAuditLogger:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @property
    def path(self) -> Path:
        return self.root / "logs" / "audit.jsonl"

    def write(
        self,
        event: str,
        message: str,
        level: str = "INFO",
        **context: Any,
    ) -> AuditEvent:
        audit_event = AuditEvent(
            event=event,
            level=level,
            message=message,
            created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            context=context,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(audit_event), separators=(",", ":")) + "\n")
        return audit_event


def read_audit_events(root: str | Path) -> list[AuditEvent]:
    path = Path(root) / "logs" / "audit.jsonl"
    if not path.exists():
        return []
    events: list[AuditEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        events.append(
            AuditEvent(
                event=payload["event"],
                level=payload["level"],
                message=payload["message"],
                created_at_utc=payload["created_at_utc"],
                context=payload.get("context", {}),
            )
        )
    return events
