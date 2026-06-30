from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from trading_bot.data_collector.models import QualityReport


def save_quality_report(report: QualityReport, root: str | Path) -> Path:
    path = Path(root) / "quality" / f"{report.symbol.replace('/', '_')}_{report.timeframe}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return path
