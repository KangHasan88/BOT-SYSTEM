# QA9 Live Go/No-Go Checklist

Live go/no-go is the final automated checklist before owner review. It does not
enable live trading and it does not authorize exchange keys.

## Command

```bash
python -m trading_bot.cli live-go-no-go-report --config config/bot.sample.toml
```

Owner approval can be represented only after manual review:

```bash
python -m trading_bot.cli live-go-no-go-report --config config/bot.sample.toml --owner-approved
```

The report is saved at:

```text
work/market_data/qa/live_go_no_go/report.json
```

## Required Evidence

- Config remains conservative and `live_enabled=false`.
- Security QA is `PASSED`.
- Risk guard drill is `PASSED`.
- VPS readiness is `PASSED`.
- Incident drill is `PASSED`.
- Paper stability is `PAPER_STABLE`.
- Data quality gate has no `BLOCKED` reports.
- Live readiness is `READY_FOR_MANUAL_REVIEW`.
- Owner approval is recorded.

## Decision

- `NO_GO`: at least one checklist item is blocked.
- `GO_FOR_OWNER_REVIEW`: automated evidence and owner approval flag are present.

Even `GO_FOR_OWNER_REVIEW` is not permission to trade live automatically. It only
means the owner can review whether a separate tiny live phase should be planned.
