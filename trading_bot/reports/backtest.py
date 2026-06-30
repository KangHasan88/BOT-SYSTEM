from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from trading_bot.backtest.metrics import BacktestMetrics


def save_backtest_metrics_report(
    metrics: BacktestMetrics,
    root: str | Path,
    symbol: str,
    timeframe: str,
) -> Path:
    path = Path(root) / "backtests" / symbol.replace("/", "_") / timeframe / "metrics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(metrics)
    if payload["profit_factor"] == float("inf"):
        payload["profit_factor"] = "inf"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
