# QA4 Risk Guard Drill

This drill verifies that safety controls stop trading before a bad day becomes a
larger loss. It is a deterministic QA command, not a live trading action.

## Command

```bash
python -m trading_bot.cli risk-guard-drill --config config/bot.sample.toml --symbol BTC/USDT
```

The report is saved at:

```text
work/market_data/qa/risk_guard_drill/report.json
```

## Required Checks

- `daily_stop`: rejects new trade when daily max loss is reached.
- `monthly_drawdown`: rejects new trade when monthly drawdown limit is reached.
- `profit_floor_stop`: stops trading when profit retraces to the daily locked floor.
- `daily_target_stop`: stops trading after daily profit target is reached.
- `position_profit_lock`: moves stop above entry after enough unrealized profit.
- `kill_switch_roundtrip`: verifies activate/read/clear behavior in a sandbox path.

## Pass Rule

The drill must return `PASSED` before production review. Any failed check blocks
deployment and must be fixed before scheduler or VPS service work continues.

The kill switch drill does not activate the real bot kill switch. It uses:

```text
work/market_data/qa/risk_guard_drill/kill_switch_sandbox
```

This keeps the production control state clean while still verifying the
underlying safety function.
