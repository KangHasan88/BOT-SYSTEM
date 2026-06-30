# Local Web Orchestrator

The local web orchestrator is the first interactive browser UI for the bot. It
runs on localhost and only exposes safe paper/research commands.

## Start

Open PowerShell from the project root:

```powershell
cd C:\Users\IT-MGR\Documents\Codex\2026-06-28\bro-2
& 'C:\Users\IT-MGR\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m trading_bot.cli serve-orchestrator --config config/bot.sample.toml --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

## Safe Actions

- validate config;
- build static dashboard;
- security QA;
- production smoke;
- live go/no-go report;
- offline-safe run cycle;
- sync latest BTC/USDT 15m;
- sync latest ETH/USDT 15m.

The candle limit input is capped at 1-1000. The orchestrator writes an
`action.lock` file while a command is running so another browser click cannot
start a conflicting command.

No live buy/sell/order button is available in this UI.

## Bot Health

The home page summarizes:

- data quality gate status;
- paper trade count and net PnL;
- live go/no-go and readiness status;
- kill switch, live flag, and security status.

Danger states such as `BLOCKED` and `NO_GO` are shown as visible badges.

## Quick Setup

The home page includes a first-run checklist for:

- config validity;
- live guard disabled;
- market data root availability;
- security QA report;
- generated dashboard;
- first recorded UI action.

The same status is available as JSON at:

```text
http://127.0.0.1:8000/api/setup
```

## Activity

Every UI action writes an activity record to:

```text
work/market_data/orchestrator/activity.jsonl
```

The latest activity output is shown on the page.

## Audit Timeline

The page also reads:

```text
work/market_data/logs/audit.jsonl
```

Audit events can be filtered by level, symbol, and timeframe. The timeline marks
`ERROR` and `CRITICAL` events clearly and refreshes periodically without
restarting the bot.
