from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from trading_bot.validation import WalkForwardReport


def save_walk_forward_report(
    report: WalkForwardReport,
    root: str | Path,
    symbol: str,
    timeframe: str,
) -> Path:
    path = Path(root) / "validation" / "walk_forward" / symbol.replace("/", "_") / f"{timeframe}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(report)
    _normalize_infinite_values(payload)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _normalize_infinite_values(value) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if item == float("inf"):
                value[key] = "inf"
            else:
                _normalize_infinite_values(item)
    elif isinstance(value, list):
        for item in value:
            _normalize_infinite_values(item)
