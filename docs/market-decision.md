# Market and Exchange Decision

## Decision

Start with `BTC/USDT` and `ETH/USDT` spot only.

## Why BTC/ETH Spot First

- High liquidity compared with small altcoins.
- Better data availability.
- Suitable for small capital.
- Can be traded without leverage.
- More stable research baseline than thin markets.
- Easier to compare strategy behavior across two major assets.

## Explicitly Excluded in v1

- Futures.
- Margin.
- Leveraged products.
- Small altcoins.
- Meme coins.
- Gold/XAUUSD live trading.

## Gold/XAUUSD Track

Gold can be researched later as a separate track. It must not be mixed with
crypto results because the market structure is different:

- trading hours are different;
- access may be via CFD/futures;
- spread and broker rules differ;
- leverage temptation is higher;
- small capital can be exposed to margin risk.

Gold becomes a candidate only after BTC/ETH research, backtest, and paper
infrastructure are stable.

Current implementation status:

- `XAUUSD` is research-only.
- `XAUUSD` is not accepted by v1 live readiness.
- Gold research must use separate data, spread, session, slippage, and broker
  rule assumptions.
- Gold must never inherit BTC/ETH spot results as proof of readiness.

## Exchange Rules for Future Live

- Use a reputable exchange/broker with clear API support.
- API key must be trading-only.
- Withdrawal permission must be disabled.
- IP whitelist should be used if available.
- Symbol metadata must be fetched before order sizing.
- Minimum notional, fee, precision, and lot size must be validated.

## Initial Data Plan

- Symbols: `BTC/USDT`, `ETH/USDT`.
- Timeframes: `15m`, `1h`, `4h`.
- Data to capture:
  - OHLCV candles;
  - spread and fee assumptions;
  - liquidity snapshots when available;
  - signal and skip reasons;
  - daily market regime labels;
  - pattern labels such as sweep, false breakout, volume spike.
