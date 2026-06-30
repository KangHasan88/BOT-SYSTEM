from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class SessionDecision:
    allowed: bool
    local_time: str
    reason: str


def parse_session_window(window: str) -> tuple[time, time]:
    parts = window.split("-")
    if len(parts) != 2:
        raise ValueError("session window must use HH:MM-HH:MM format")
    start = _parse_time(parts[0])
    end = _parse_time(parts[1])
    if start == end:
        raise ValueError("session window start and end cannot be equal")
    return start, end


def is_entry_allowed_at_ms(
    open_time_ms: int,
    windows: tuple[str, ...],
    timezone_name: str = "Asia/Jakarta",
) -> SessionDecision:
    local_dt = datetime.fromtimestamp(open_time_ms / 1000, tz=ZoneInfo(timezone_name))
    allowed = is_time_in_windows(local_dt.time(), windows)
    local_text = local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    if allowed:
        return SessionDecision(True, local_text, "inside configured entry window")
    return SessionDecision(False, local_text, "outside configured entry window")


def is_time_in_windows(value: time, windows: tuple[str, ...]) -> bool:
    for window in windows:
        start, end = parse_session_window(window)
        if start < end:
            if start <= value <= end:
                return True
        else:
            if value >= start or value <= end:
                return True
    return False


def _parse_time(value: str) -> time:
    try:
        hour_text, minute_text = value.strip().split(":")
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise ValueError("time must use HH:MM format") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("time must be within 00:00-23:59")
    return time(hour=hour, minute=minute)
