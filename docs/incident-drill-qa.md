# QA8 Incident Drill

Incident drill verifies that operational failures produce a clear safe response,
an audit trail, and an alert before the bot is allowed toward production.

## Command

```bash
python -m trading_bot.cli incident-drill-report --config config/bot.sample.toml --symbol BTC/USDT
```

The report is saved at:

```text
work/market_data/qa/incident_drill/report.json
```

## Scenarios

- `exchange_api_down`: skip sync and block new entries.
- `network_down`: do not trade on stale data.
- `bot_crash`: require operator review before restart.

## Pass Rule

Each scenario must write:

- one audit event;
- one alert outbox message;
- one explicit safe response.

The report must be `PASSED` before production smoke testing.
