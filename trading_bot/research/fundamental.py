from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig


ALLOWED_EVENT_CATEGORIES = ["news", "macro", "exchange", "liquidity", "maintenance", "other"]
ALLOWED_EVENT_RISKS = ["LOW", "MEDIUM", "HIGH", "BLOCK"]


@dataclass(frozen=True)
class FundamentalEvent:
    symbol: str
    category: str
    risk: str
    title: str
    note: str
    source: str
    event_time_utc: str
    created_at_utc: str


@dataclass(frozen=True)
class FundamentalReport:
    status: str
    generated_at_utc: str
    event_path: str
    total_events: int
    high_or_block_events: int
    top_risk: str
    color: str
    summary: str
    guardrail: str
    risk_counts: dict[str, int]
    category_counts: dict[str, int]
    events: list[FundamentalEvent] = field(default_factory=list)


def add_fundamental_event(
    config: BotConfig,
    symbol: str,
    category: str,
    risk: str,
    title: str,
    note: str = "",
    source: str = "manual",
    event_time_utc: str = "",
    event_path: str | Path | None = None,
) -> FundamentalEvent:
    normalized_category = category.strip().lower() or "other"
    normalized_risk = risk.strip().upper()
    if symbol not in config.symbols:
        raise ValueError(f"symbol is not configured: {symbol}")
    if normalized_category not in ALLOWED_EVENT_CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(ALLOWED_EVENT_CATEGORIES)}")
    if normalized_risk not in ALLOWED_EVENT_RISKS:
        raise ValueError(f"risk must be one of: {', '.join(ALLOWED_EVENT_RISKS)}")
    event = FundamentalEvent(
        symbol=symbol,
        category=normalized_category,
        risk=normalized_risk,
        title=title.strip(),
        note=note.strip(),
        source=source.strip() or "manual",
        event_time_utc=event_time_utc.strip() or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    path = _event_path(config, event_path)
    payload = _read_event_payload(path)
    payload["events"].append(asdict(event))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return event


def build_fundamental_report(
    config: BotConfig,
    event_path: str | Path | None = None,
    limit: int = 12,
) -> FundamentalReport:
    path = _event_path(config, event_path)
    events = _load_events(config, path)
    risk_counts = Counter(event.risk for event in events)
    category_counts = Counter(event.category for event in events)
    top_risk = _top_risk(risk_counts)
    high_or_block = risk_counts.get("HIGH", 0) + risk_counts.get("BLOCK", 0)
    status = "FUNDAMENTAL_CLEAR" if not events else "FUNDAMENTAL_REVIEW"
    if risk_counts.get("BLOCK", 0):
        status = "FUNDAMENTAL_BLOCK"
    elif risk_counts.get("HIGH", 0):
        status = "FUNDAMENTAL_HIGH_RISK"
    return FundamentalReport(
        status=status,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        event_path=str(path),
        total_events=len(events),
        high_or_block_events=high_or_block,
        top_risk=top_risk,
        color=_risk_color(top_risk),
        summary=_summary(len(events), high_or_block, top_risk),
        guardrail="Fundamental lane is review-only. HIGH/BLOCK risk should pause new paper/live decisions until owner review.",
        risk_counts=dict(risk_counts),
        category_counts=dict(category_counts),
        events=events[-limit:],
    )


def save_fundamental_report(report: FundamentalReport, root: str | Path) -> Path:
    path = Path(root) / "reports" / "fundamental" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _event_path(config: BotConfig, event_path: str | Path | None) -> Path:
    if event_path is not None:
        return Path(event_path)
    return Path(config.data_root) / "reports" / "fundamental" / "events.json"


def _read_event_payload(path: Path) -> dict:
    if not path.exists():
        return {"events": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"events": []}
    if not isinstance(payload, dict) or not isinstance(payload.get("events", []), list):
        return {"events": []}
    return {"events": payload.get("events", [])}


def _load_events(config: BotConfig, path: Path) -> list[FundamentalEvent]:
    events: list[FundamentalEvent] = []
    for row in _read_event_payload(path)["events"]:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol", ""))
        category = str(row.get("category", "other")).strip().lower()
        risk = str(row.get("risk", "LOW")).strip().upper()
        if symbol not in config.symbols or category not in ALLOWED_EVENT_CATEGORIES or risk not in ALLOWED_EVENT_RISKS:
            continue
        events.append(
            FundamentalEvent(
                symbol=symbol,
                category=category,
                risk=risk,
                title=str(row.get("title", "")),
                note=str(row.get("note", "")),
                source=str(row.get("source", "manual")),
                event_time_utc=str(row.get("event_time_utc", "")),
                created_at_utc=str(row.get("created_at_utc", "")),
            )
        )
    return events


def _top_risk(counts: Counter[str]) -> str:
    for risk in ["BLOCK", "HIGH", "MEDIUM", "LOW"]:
        if counts.get(risk, 0):
            return risk
    return "LOW"


def _risk_color(risk: str) -> str:
    return {
        "LOW": "green",
        "MEDIUM": "yellow",
        "HIGH": "orange",
        "BLOCK": "red",
    }.get(risk, "green")


def _summary(total: int, high_or_block: int, top_risk: str) -> str:
    if total == 0:
        return "belum ada event fundamental manual; default clear untuk demo"
    return f"{total} event fundamental terbaca, {high_or_block} high/block, top risk={top_risk}"
