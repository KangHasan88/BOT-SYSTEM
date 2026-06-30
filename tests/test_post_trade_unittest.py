from pathlib import Path
import csv
import json
import tempfile
import unittest

from trading_bot.paper.models import PaperTrade
from trading_bot.post_trade import (
    generate_post_trade_report,
    load_paper_trades,
    save_post_trade_report,
)


def trade(entry_time_ms: int, net_pnl: float, exit_reason: str = "EXIT_SIGNAL") -> PaperTrade:
    return PaperTrade(
        symbol="BTC/USDT",
        timeframe="15m",
        entry_time_ms=entry_time_ms,
        exit_time_ms=entry_time_ms + 900_000,
        entry_price=100.0,
        exit_price=101.0 if net_pnl >= 0 else 99.0,
        quantity=1.0,
        gross_pnl=net_pnl,
        fees=0.0,
        net_pnl=net_pnl,
        exit_reason=exit_reason,
    )


class PostTradeTest(unittest.TestCase):
    def test_empty_report(self) -> None:
        report = generate_post_trade_report([], "BTC/USDT", "15m")

        self.assertEqual(report.summary.trade_count, 0)
        self.assertIn("collect more paper trades", report.recommendations[0])

    def test_trade_summary_and_recommendations(self) -> None:
        trades = [
            trade(1782700200000, 10.0),
            trade(1782703800000, -5.0, "STOP_LOSS"),
            trade(1782790200000, -7.0, "STOP_LOSS"),
        ]
        report = generate_post_trade_report(trades)

        self.assertEqual(report.summary.trade_count, 3)
        self.assertEqual(report.summary.win_count, 1)
        self.assertLess(report.summary.total_net_pnl, 0)
        self.assertTrue(any("strategy iteration" in item for item in report.recommendations))

    def test_save_post_trade_report(self) -> None:
        report = generate_post_trade_report([trade(1782700200000, 10.0)])
        with tempfile.TemporaryDirectory() as temp_dir:
            path = save_post_trade_report(report, Path(temp_dir))
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(path.name.endswith(".json"))
        self.assertEqual(payload["symbol"], "BTC/USDT")
        self.assertIn("summary", payload)

    def test_load_paper_trades(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "paper" / "BTC_USDT" / "15m" / "trades.csv"
            path.parent.mkdir(parents=True)
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(trade(1, 1.0).__dict__.keys()))
                writer.writeheader()
                writer.writerow(trade(1, 1.0).__dict__)

            trades = load_paper_trades(temp_dir, "BTC/USDT", "15m")

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].net_pnl, 1.0)


if __name__ == "__main__":
    unittest.main()
