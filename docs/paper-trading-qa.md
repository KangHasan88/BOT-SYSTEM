# QA3 Paper Trading Stability Review

Paper trading is the mandatory proving ground before any future live review. The
bot must prove it can run, stop, reject weak setups, and report problems without
using real exchange execution.

## Stability Window

- Minimum review window: 14 calendar days.
- Preferred review window: 28 calendar days.
- Minimum completed paper trades: 20.
- Critical audit errors allowed: 0.
- Live trading remains disabled even when this report passes.

## Command

```bash
python -m trading_bot.cli paper-stability-report --config config/bot.sample.toml --symbol BTC/USDT --timeframe 15m --min-days 14 --min-trades 20
```

The report is saved at:

```text
work/market_data/qa/paper_stability/BTC_USDT/15m/report.json
```

## Decision Rules

`PAPER_STABLE` means the paper data has enough time, enough trades, and zero
critical audit errors for owner review. It does not authorize live trading.

`BLOCKED` means at least one hard requirement is missing. Common blockers:

- Too few observed paper days.
- Too few completed paper trades.
- One or more `ERROR` or `CRITICAL` audit events.

Warnings do not block by themselves, but must be reviewed before improving the
strategy:

- Rejected order rate above 35%.
- Stop-loss exit rate above 60%.

## Manual Review

- Check whether profit came from a few lucky trades or consistent behavior.
- Review rejected order reasons; many rejects can mean risk settings are too
  tight or market quality is poor.
- Review stop-loss concentration by hour/session before widening targets.
- Keep the kill switch and daily profit lock enabled during paper testing.
- Continue daily capture so pattern research can compare trades against the
  market regime and liquidity context.
