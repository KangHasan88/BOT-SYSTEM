# QA5 Data Quality Gate

The bot must not trust market data until the data quality gate has checked the
dataset. Bad candles can make backtests, paper trading, and future live decisions
look better or worse than reality.

## Command

```bash
python -m trading_bot.cli data-quality-gate --config config/bot.sample.toml --symbol BTC/USDT --timeframe 15m
```

For deterministic stale-data smoke tests:

```bash
python -m trading_bot.cli data-quality-gate --config config/bot.sample.toml --symbol BTC/USDT --timeframe 15m --now-ms 1782700200000
```

The report is saved at:

```text
work/market_data/qa/data_quality_gate/BTC_USDT/15m/report.json
```

## Blocking Rules

`BLOCKED` means strategy/backtest/paper/live review should not use this dataset.
The default blockers are:

- no candles;
- any missing candle gap;
- any duplicate candle open time;
- any non-positive OHLC price;
- any `high < low` malformed candle;
- stale feed older than 3 completed candles.

## Warning Rules

`WARN` means the dataset is usable for research but should be reviewed before
trusting conclusions. The default warning is:

- zero-volume candles above 5% of the dataset.

## Operating Notes

- Run this gate after sync/backfill and before interpreting signals.
- If stale data is blocked, sync latest public OHLCV before rerunning strategy.
- If gaps persist after sync, use backfill before running backtest or paper.
- If malformed candles appear, quarantine the dataset and verify the source.
