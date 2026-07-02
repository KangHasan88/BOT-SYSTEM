from pathlib import Path
import tempfile
import unittest

from trading_bot.data_collector import Candle
from trading_bot.data_collector.market_context import SymbolMetadata
from trading_bot.paper import PaperConfig, PaperCsvStore, run_paper_session


def metadata(min_notional: float = 1.0) -> SymbolMetadata:
    return SymbolMetadata("BTC/USDT", "BTC", "USDT", min_notional, 8, 8, 0.10, 0.10)


def uptrend_candles(count: int = 80) -> list[Candle]:
    candles: list[Candle] = []
    price = 100.0
    for index in range(count):
        price += 0.05
        close_offset = 0.08
        if index % 6 == 0:
            price -= 0.10
            close_offset = -0.08
        candles.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                open_time_ms=(index + 1) * 900_000,
                open=price,
                high=price + 0.55,
                low=price - 0.35,
                close=price + close_offset,
                volume=100.0,
            )
        )
    return candles


class PaperSimulatorTest(unittest.TestCase):
    def test_empty_session(self) -> None:
        result = run_paper_session([], metadata())

        self.assertEqual(result.final_equity, 1_000.0)
        self.assertEqual(result.orders, [])
        self.assertEqual(result.trades, [])

    def test_uptrend_generates_virtual_orders_and_trades(self) -> None:
        result = run_paper_session(uptrend_candles(), metadata())

        self.assertGreaterEqual(len(result.account_snapshots), len(uptrend_candles()))
        self.assertGreaterEqual(len(result.orders), 2)
        self.assertGreaterEqual(len(result.trades), 1)
        self.assertTrue(all(order.status in {"FILLED", "REJECTED"} for order in result.orders))

    def test_risk_rejection_is_journaled(self) -> None:
        result = run_paper_session(uptrend_candles(), metadata(min_notional=10_000_000.0))

        self.assertTrue(any(order.status == "REJECTED" for order in result.orders))
        self.assertEqual(result.trades, [])

    def test_paper_csv_export(self) -> None:
        result = run_paper_session(uptrend_candles(), metadata())
        with tempfile.TemporaryDirectory() as temp_dir:
            orders_path, trades_path, account_path = PaperCsvStore(Path(temp_dir)).write(result)

            self.assertTrue(orders_path.exists())
            self.assertTrue(trades_path.exists())
            self.assertTrue(account_path.exists())
            self.assertIn("status", orders_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertIn("equity", account_path.read_text(encoding="utf-8").splitlines()[0])

    def test_fee_and_slippage_reduce_final_equity(self) -> None:
        no_cost = run_paper_session(
            uptrend_candles(),
            metadata(),
            PaperConfig(fee_pct=0.0, slippage_pct=0.0),
        )
        with_cost = run_paper_session(
            uptrend_candles(),
            metadata(),
            PaperConfig(fee_pct=0.10, slippage_pct=0.02),
        )

        self.assertLess(with_cost.final_equity, no_cost.final_equity)

    def test_account_snapshots_include_unrealized_pnl_for_open_positions(self) -> None:
        result = run_paper_session(uptrend_candles(), metadata())

        open_snapshots = [snapshot for snapshot in result.account_snapshots if snapshot.open_positions]

        self.assertTrue(open_snapshots)
        self.assertTrue(any(snapshot.unrealized_pnl != 0 for snapshot in open_snapshots))
        self.assertTrue(all(snapshot.marked_equity == snapshot.equity + snapshot.unrealized_pnl for snapshot in open_snapshots))


if __name__ == "__main__":
    unittest.main()
