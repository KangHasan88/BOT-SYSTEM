import unittest

from trading_bot.data_collector.market_context import SymbolMetadata
from trading_bot.risk_manager import (
    AccountState,
    RiskConfig,
    TradeCandidate,
    evaluate_trade_risk,
)


def account(**overrides) -> AccountState:
    values = {
        "equity": 1_000.0,
        "day_start_equity": 1_000.0,
        "month_start_equity": 1_000.0,
        "open_positions": 0,
        "consecutive_losses_today": 0,
    }
    values.update(overrides)
    return AccountState(**values)


def candidate(**overrides) -> TradeCandidate:
    values = {
        "symbol": "BTC/USDT",
        "side": "buy",
        "entry_price": 100.0,
        "stop_price": 99.0,
        "confidence": 0.5,
    }
    values.update(overrides)
    return TradeCandidate(**values)


def metadata(min_notional: float = 1.0) -> SymbolMetadata:
    return SymbolMetadata(
        symbol="BTC/USDT",
        base_asset="BTC",
        quote_asset="USDT",
        min_notional=min_notional,
        price_precision=8,
        quantity_precision=8,
        taker_fee_pct=0.10,
        maker_fee_pct=0.10,
    )


class RiskManagerTest(unittest.TestCase):
    def test_approved_trade_sizes_by_risk(self) -> None:
        decision = evaluate_trade_risk(account(), candidate(), metadata())

        self.assertEqual(decision.status, "APPROVED")
        self.assertAlmostEqual(decision.risk_amount, 2.5)
        self.assertAlmostEqual(decision.quantity, 2.5)
        self.assertAlmostEqual(decision.notional, 250.0)

    def test_reject_max_open_positions(self) -> None:
        decision = evaluate_trade_risk(account(open_positions=1), candidate(), metadata())

        self.assertEqual(decision.status, "REJECTED")
        self.assertIn("max open positions", decision.reason)

    def test_reject_daily_max_loss(self) -> None:
        decision = evaluate_trade_risk(account(equity=989.0), candidate(), metadata())

        self.assertEqual(decision.status, "REJECTED")
        self.assertIn("daily max loss", decision.reason)

    def test_reject_monthly_max_drawdown(self) -> None:
        decision = evaluate_trade_risk(
            account(equity=949.0, day_start_equity=1_000.0, month_start_equity=1_000.0),
            candidate(),
            metadata(),
        )

        self.assertEqual(decision.status, "REJECTED")
        self.assertIn("daily max loss", decision.reason)

    def test_reject_monthly_when_daily_ok(self) -> None:
        decision = evaluate_trade_risk(
            account(equity=949.0, day_start_equity=950.0, month_start_equity=1_000.0),
            candidate(),
            metadata(),
        )

        self.assertEqual(decision.status, "REJECTED")
        self.assertIn("monthly max drawdown", decision.reason)

    def test_reject_stop_too_tight_or_wide(self) -> None:
        tight = evaluate_trade_risk(account(), candidate(stop_price=99.95), metadata())
        wide = evaluate_trade_risk(account(), candidate(stop_price=90.0), metadata())

        self.assertEqual(tight.status, "REJECTED")
        self.assertIn("too tight", tight.reason)
        self.assertEqual(wide.status, "REJECTED")
        self.assertIn("too wide", wide.reason)

    def test_reject_min_notional(self) -> None:
        decision = evaluate_trade_risk(account(), candidate(), metadata(min_notional=500.0))

        self.assertEqual(decision.status, "REJECTED")
        self.assertIn("below min_notional", decision.reason)

    def test_reject_non_buy_in_spot_v1(self) -> None:
        decision = evaluate_trade_risk(account(), candidate(side="sell"), metadata())

        self.assertEqual(decision.status, "REJECTED")
        self.assertIn("v1 only supports buy", decision.reason)


if __name__ == "__main__":
    unittest.main()
