from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig


ALLOWED_FEEDBACK_LABELS = [
    "setup_bagus",
    "entry_telat",
    "exit_cepat",
    "market_sideways",
    "news_risk",
    "false_signal",
    "risk_terlalu_besar",
    "profit_lock_bagus",
    "skip_benar",
    "perlu_eksperimen",
]


@dataclass(frozen=True)
class HumanFeedbackLabel:
    symbol: str
    timeframe: str
    label: str
    note: str
    reviewer: str
    confidence: str
    created_at_utc: str


@dataclass(frozen=True)
class HumanFeedbackLesson:
    label: str
    count: int
    lesson: str
    next_action: str


@dataclass(frozen=True)
class HumanFeedbackReport:
    status: str
    generated_at_utc: str
    label_path: str
    total_labels: int
    pairs_labeled: int
    top_label: str
    summary: str
    guardrail: str
    allowed_labels: list[str]
    label_counts: dict[str, int]
    pair_counts: dict[str, int]
    recent_labels: list[HumanFeedbackLabel] = field(default_factory=list)
    lessons: list[HumanFeedbackLesson] = field(default_factory=list)


def add_human_feedback_label(
    config: BotConfig,
    symbol: str,
    timeframe: str,
    label: str,
    note: str,
    reviewer: str = "owner",
    confidence: str = "manual",
    label_path: str | Path | None = None,
) -> HumanFeedbackLabel:
    normalized_label = _normalize_label(label)
    if normalized_label not in ALLOWED_FEEDBACK_LABELS:
        raise ValueError(f"label must be one of: {', '.join(ALLOWED_FEEDBACK_LABELS)}")
    if symbol not in config.symbols:
        raise ValueError(f"symbol is not configured: {symbol}")
    if timeframe not in config.timeframes:
        raise ValueError(f"timeframe is not configured: {timeframe}")
    feedback = HumanFeedbackLabel(
        symbol=symbol,
        timeframe=timeframe,
        label=normalized_label,
        note=note.strip(),
        reviewer=reviewer.strip() or "owner",
        confidence=confidence.strip() or "manual",
        created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    path = _label_path(config, label_path)
    payload = _read_label_payload(path)
    payload["labels"].append(asdict(feedback))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return feedback


def build_human_feedback_report(
    config: BotConfig,
    label_path: str | Path | None = None,
    limit: int = 10,
) -> HumanFeedbackReport:
    path = _label_path(config, label_path)
    labels = _load_labels(path)
    label_counts = Counter(label.label for label in labels)
    pair_counts = Counter(f"{label.symbol} {label.timeframe}" for label in labels)
    lessons = [_lesson(label, count) for label, count in label_counts.most_common()]
    status = "HUMAN_FEEDBACK_ACTIVE" if labels else "HUMAN_FEEDBACK_EMPTY"
    top_label = label_counts.most_common(1)[0][0] if label_counts else "-"
    return HumanFeedbackReport(
        status=status,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        label_path=str(path),
        total_labels=len(labels),
        pairs_labeled=len(pair_counts),
        top_label=top_label,
        summary=_summary(len(labels), top_label),
        guardrail="Human feedback can update lessons and experiments, but must never place live orders.",
        allowed_labels=list(ALLOWED_FEEDBACK_LABELS),
        label_counts=dict(label_counts),
        pair_counts=dict(pair_counts),
        recent_labels=labels[-limit:],
        lessons=lessons,
    )


def save_human_feedback_report(report: HumanFeedbackReport, root: str | Path) -> Path:
    path = Path(root) / "reports" / "learning" / "human_feedback.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _label_path(config: BotConfig, label_path: str | Path | None) -> Path:
    if label_path is not None:
        return Path(label_path)
    return Path(config.data_root) / "reports" / "learning" / "manual_labels.json"


def _read_label_payload(path: Path) -> dict:
    if not path.exists():
        return {"labels": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"labels": []}
    if not isinstance(payload, dict) or not isinstance(payload.get("labels", []), list):
        return {"labels": []}
    return {"labels": payload.get("labels", [])}


def _load_labels(path: Path) -> list[HumanFeedbackLabel]:
    labels: list[HumanFeedbackLabel] = []
    for row in _read_label_payload(path)["labels"]:
        if not isinstance(row, dict):
            continue
        label = _normalize_label(str(row.get("label", "")))
        if label not in ALLOWED_FEEDBACK_LABELS:
            continue
        labels.append(
            HumanFeedbackLabel(
                symbol=str(row.get("symbol", "")),
                timeframe=str(row.get("timeframe", "")),
                label=label,
                note=str(row.get("note", "")),
                reviewer=str(row.get("reviewer", "owner")),
                confidence=str(row.get("confidence", "manual")),
                created_at_utc=str(row.get("created_at_utc", "")),
            )
        )
    return [label for label in labels if label.symbol and label.timeframe]


def _lesson(label: str, count: int) -> HumanFeedbackLesson:
    lessons = {
        "setup_bagus": ("setup ini bisa dipertahankan sebagai contoh pembanding", "Tandai pola serupa saat paper review"),
        "entry_telat": ("entry sering terlambat; cek filter konfirmasi dan jarak dari trigger", "Review candle sebelum entry"),
        "exit_cepat": ("exit terlalu cepat bisa memotong profit", "Bandingkan dengan profit lock dan trailing rule"),
        "market_sideways": ("market sideways perlu filter tambahan", "Cek regime sebelum entry"),
        "news_risk": ("risiko news perlu blokir manual", "Tambahkan event/fundamental lane"),
        "false_signal": ("sinyal palsu harus masuk review filter", "Cek volume, wick, dan confirmation"),
        "risk_terlalu_besar": ("risk harus diperkecil sebelum eksperimen lanjut", "Review sizing dan SL distance"),
        "profit_lock_bagus": ("profit lock bekerja baik", "Pertahankan rule lock saat paper campaign"),
        "skip_benar": ("skip membantu menghindari trade buruk", "Cari pola skip yang perlu diautomasi"),
        "perlu_eksperimen": ("ide ini masuk backlog eksperimen", "Masukkan ke strategy experiment registry"),
    }
    lesson, next_action = lessons[label]
    return HumanFeedbackLesson(label, count, lesson, next_action)


def _summary(total_labels: int, top_label: str) -> str:
    if total_labels == 0:
        return "belum ada human feedback label; tambah label setelah review chart/trade"
    return f"{total_labels} feedback label terbaca, top label={top_label}"


def _normalize_label(label: str) -> str:
    return label.strip().lower().replace(" ", "_").replace("-", "_")
