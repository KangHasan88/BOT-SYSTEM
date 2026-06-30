from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_EXCLUDES = {".git", "__pycache__", ".pytest_cache", "work", "tests"}
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(exchange_api_key|api_key|apikey)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{16,})"),
    re.compile(r"(?i)\b(exchange_api_secret|api_secret|secret_key)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-+/=]{16,})"),
    re.compile(r"(?i)\b(binance|bybit|okx)[_\-]?(secret|key)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-+/=]{16,})"),
)


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line_number: int
    pattern: str


def scan_for_secrets(root: str | Path, excludes: set[str] | None = None) -> list[SecretFinding]:
    base = Path(root)
    excluded = excludes or DEFAULT_EXCLUDES
    findings: list[SecretFinding] = []
    for path in base.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.parts):
            continue
        if path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz"}:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for pattern in SECRET_PATTERNS:
                match = pattern.search(line)
                if match and not _is_placeholder(match.group(match.lastindex or 1)):
                    findings.append(
                        SecretFinding(
                            path=str(path),
                            line_number=line_number,
                            pattern=pattern.pattern,
                        )
                    )
    return findings


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return lowered in {"changeme", "placeholder", "example", "dummy", "test"} or lowered.startswith("<")
