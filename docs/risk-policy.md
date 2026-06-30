# Risk Policy and No-Live Guard

## Goal

This bot must become a disciplined research and execution system. It must never
be allowed to trade live just because a strategy looks promising in one test.

## Phases

1. `research`: collect data, compute features, label patterns, and produce
   recommendations. No order placement is allowed.
2. `backtest`: replay historical data and evaluate strategy versions. No order
   placement is allowed.
3. `paper`: simulate account, positions, fills, risk limits, and daily reports.
   No real money is touched.
4. `live`: disabled by default. May only be enabled after live readiness is
   manually approved.

## Hard Rules

- Live trading is disabled by default.
- Spot only for v1.
- No futures.
- No margin.
- No leverage.
- No withdrawal permission is ever required for API keys.
- Initial allowlist: `BTC/USDT`, `ETH/USDT`.
- Max open position in v1: `1`.
- Every trade must pass the risk manager.
- Every signal must have a written reason.
- Every skip/reject must be logged.

## Risk Limits

Default conservative profile:

- Risk per trade: `0.25%` of account equity.
- Maximum risk per trade during aggressive experiments: `0.50%`.
- Daily max loss: `1.00%` hard stop.
- Monthly max drawdown: `5.00%` hard stop.
- Two consecutive losses in one day: stop for the day.
- Data stale or spread abnormal: no new entries.

## Profit Lock

Profit is flexible, loss is hard.

- Daily profit lock trigger: `0.50%`.
- After trigger, lock at least `60%` of daily profit.
- If equity falls back to the locked floor, stop new trading for the day.
- At `1R` open profit, move stop toward break-even if strategy permits.
- At daily target hit, live trading stops or switches to conservative mode.

## Learning Guard

Research and AI/ML modules may suggest enhancements, but they must not:

- change live strategy parameters automatically;
- place live orders;
- bypass risk manager;
- disable hard stops;
- promote a strategy without backtest and paper validation.

## Live Readiness Gate

Live mode requires all of these:

- backtest passes agreed thresholds;
- paper trading runs for at least 2-4 weeks;
- no critical data/execution bug is open;
- kill switch is tested;
- profit lock and daily stop are tested;
- API key is trading-only with withdrawal disabled;
- manual approval is recorded.
