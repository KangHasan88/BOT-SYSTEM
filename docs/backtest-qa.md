# QA2 Backtest QA

Backtest must be conservative enough to avoid giving false confidence.

## Timing Policy

- Signals are generated from a completed candle.
- Entry and exit signals are executed on the next candle open with slippage.
- Stop-loss simulation can trigger inside the next candle if price crosses stop.
- A trade fails no-lookahead audit if `entry_time_ms <= entry_signal_time_ms`.
- A trade fails no-lookahead audit if `exit_time_ms <= exit_signal_time_ms`.

## Cost Policy

Backtest metrics report:

- `gross_return_pct`
- `total_gross_pnl`
- `total_net_pnl`
- `total_fees`
- `fee_pct`
- `slippage_pct`

The strategy must be rejected when it is only profitable before costs.

## Promotion Gate

A strategy cannot become `PAPER_CANDIDATE` unless:

- sample size reaches the configured threshold;
- no-lookahead audit passes;
- net return and expectancy are positive;
- max drawdown stays within conservative threshold;
- profit factor passes threshold;
- losing streak is acceptable.

## Standard Commands

```bash
python -m trading_bot.cli backtest-report --symbol BTC/USDT --timeframe 15m --initial-equity 1000
python -m unittest discover tests "*_unittest.py"
```
