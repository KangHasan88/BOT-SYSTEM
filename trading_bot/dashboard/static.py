from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path


@dataclass(frozen=True)
class DashboardData:
    daily_reports: list[dict]
    backtest_metrics: list[dict]
    paper_accounts: list[dict]
    paper_trades: list[dict]


def load_dashboard_data(root: str | Path) -> DashboardData:
    base = Path(root)
    return DashboardData(
        daily_reports=_load_json_files(base / "reports" / "daily"),
        backtest_metrics=_load_json_files(base / "backtests"),
        paper_accounts=_load_csv_files(base / "paper", "account.csv"),
        paper_trades=_load_csv_files(base / "paper", "trades.csv"),
    )


def save_review_dashboard(root: str | Path) -> Path:
    base = Path(root)
    data = load_dashboard_data(base)
    html = build_review_dashboard(data)
    path = base / "dashboard" / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def build_review_dashboard(data: DashboardData) -> str:
    latest_reports = sorted(
        data.daily_reports,
        key=lambda row: str(row.get("report_date_utc", "")),
        reverse=True,
    )[:10]
    latest_paper_equity = _latest_float(data.paper_accounts, "equity")
    latest_backtest = data.backtest_metrics[0] if data.backtest_metrics else {}
    total_paper_pnl = sum(_float(row.get("net_pnl")) for row in data.paper_trades)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Bot Review Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #607080;
      --line: #d7dee6;
      --panel: #ffffff;
      --page: #f4f7fa;
      --accent: #0f766e;
      --warn: #b45309;
      --bad: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--page);
      color: var(--ink);
    }}
    header {{
      padding: 24px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 92px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 10px;
    }}
    .metric strong {{
      font-size: 22px;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    section {{
      margin-bottom: 24px;
    }}
    h2 {{
      font-size: 16px;
      margin: 0 0 10px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      font-size: 13px;
      vertical-align: top;
    }}
    th {{
      background: #edf3f7;
      color: #334155;
      font-weight: 700;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .status {{
      display: inline-block;
      min-width: 96px;
      padding: 3px 8px;
      border-radius: 999px;
      background: #e6f4f1;
      color: var(--accent);
      text-align: center;
      font-size: 12px;
      font-weight: 700;
    }}
    .status.review {{ background: #fff4e5; color: var(--warn); }}
    .status.no-data {{ background: #f1f5f9; color: #475569; }}
    .empty {{
      padding: 18px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <header>
    <h1>Trading Bot Review Dashboard</h1>
  </header>
  <main>
    <div class="metrics">
      {_metric("Daily Reports", len(data.daily_reports))}
      {_metric("Latest Paper Equity", _fmt(latest_paper_equity))}
      {_metric("Paper Net PnL", _fmt(total_paper_pnl))}
      {_metric("Backtest Gate", latest_backtest.get("recommendation", "N/A"))}
    </div>
    <section>
      <h2>Daily Research</h2>
      {_daily_report_table(latest_reports)}
    </section>
    <section>
      <h2>Backtest Metrics</h2>
      {_backtest_table(data.backtest_metrics[:10])}
    </section>
    <section>
      <h2>Paper Trades</h2>
      {_paper_trade_table(data.paper_trades[-20:])}
    </section>
  </main>
</body>
</html>
"""


def _metric(label: str, value: object) -> str:
    return f'<div class="metric"><span>{escape(str(label))}</span><strong>{escape(str(value))}</strong></div>'


def _daily_report_table(rows: list[dict]) -> str:
    if not rows:
        return '<div class="empty">No daily reports yet.</div>'
    body = []
    for row in rows:
        status = str(row.get("review_status", "NEUTRAL"))
        status_class = "review" if status == "REVIEW_REQUIRED" else "no-data" if status == "NO_DATA" else ""
        body.append(
            "<tr>"
            f"<td>{escape(str(row.get('report_date_utc', '')))}</td>"
            f"<td>{escape(str(row.get('symbol', '')))}</td>"
            f"<td>{escape(str(row.get('timeframe', '')))}</td>"
            f"<td>{escape(str(row.get('dominant_regime', '')))}</td>"
            f'<td><span class="status {status_class}">{escape(status)}</span></td>'
            f"<td>{escape('; '.join(row.get('notes', [])))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Date</th><th>Symbol</th><th>TF</th><th>Regime</th>"
        "<th>Status</th><th>Notes</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def _backtest_table(rows: list[dict]) -> str:
    if not rows:
        return '<div class="empty">No backtest metrics yet.</div>'
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{escape(str(row.get('recommendation', '')))}</td>"
            f"<td>{escape(str(row.get('trade_count', '')))}</td>"
            f"<td>{escape(str(row.get('win_rate_pct', '')))}</td>"
            f"<td>{escape(str(row.get('max_drawdown_pct', '')))}</td>"
            f"<td>{escape(str(row.get('profit_factor', '')))}</td>"
            f"<td>{escape(str(row.get('reason', '')))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Gate</th><th>Trades</th><th>Win %</th><th>Max DD %</th>"
        "<th>PF</th><th>Reason</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def _paper_trade_table(rows: list[dict]) -> str:
    if not rows:
        return '<div class="empty">No paper trades yet.</div>'
    body = []
    for row in reversed(rows):
        body.append(
            "<tr>"
            f"<td>{escape(str(row.get('symbol', '')))}</td>"
            f"<td>{escape(str(row.get('timeframe', '')))}</td>"
            f"<td>{escape(str(row.get('entry_price', '')))}</td>"
            f"<td>{escape(str(row.get('exit_price', '')))}</td>"
            f"<td>{escape(str(row.get('net_pnl', '')))}</td>"
            f"<td>{escape(str(row.get('exit_reason', '')))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Symbol</th><th>TF</th><th>Entry</th><th>Exit</th>"
        "<th>Net PnL</th><th>Reason</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def _load_json_files(root: Path) -> list[dict]:
    if not root.exists():
        return []
    rows: list[dict] = []
    for path in sorted(root.rglob("*.json"), reverse=True):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return rows


def _load_csv_files(root: Path, filename: str) -> list[dict]:
    if not root.exists():
        return []
    rows: list[dict] = []
    for path in sorted(root.rglob(filename)):
        with path.open("r", newline="", encoding="utf-8") as handle:
            if path.stat().st_size == 0:
                continue
            rows.extend(csv.DictReader(handle))
    return rows


def _latest_float(rows: list[dict], field: str) -> float | None:
    if not rows:
        return None
    return _float(rows[-1].get(field))


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)
