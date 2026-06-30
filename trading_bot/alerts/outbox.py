from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from trading_bot.alerts.core import AlertMessage


class AlertOutbox:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, message: AlertMessage) -> Path:
        path = self.root / "alerts" / "outbox" / f"{message.created_at_utc.replace(':', '-')}-{message.kind}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(message), indent=2), encoding="utf-8")
        return path
