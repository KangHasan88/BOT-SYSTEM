from pathlib import Path
import json
import tempfile
import unittest

from trading_bot.backtest import BacktestConfig, run_event_backtest
from trading_bot.data_collector import Candle
from trading_bot.data_collector.market_context import SymbolMetadata
from trading_bot.paper import PaperConfig, run_paper_session
from trading_bot.reports.daily_journal import generate_daily_market_journal, save_daily_market_journal


def metadata() -> SymbolMetadata:
    return SymbolMetadata("BTC/USDT", "BTC", "USDT", 1.0, 8, 8, 0.10, 0.10)


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


class DailyJournalTest(unittest.TestCase):
    def test_empty_journal(self) -> None:
        journal = generate_daily_market_journal([])

        self.assertEqual(journal.review_status, "NO_DATA")
        self.assertEqual(journal.candle_count, 0)

    def test_generates_daily_summary(self) -> None:
        candles = uptrend_candles()
        paper = run_paper_session(candles, metadata(), PaperConfig(fee_pct=0.0, slippage_pct=0.0))
        backtest = run_event_backtest(candles, metadata(), BacktestConfig(fee_pct=0.0, slippage_pct=0.0))

        journal = generate_daily_market_journal(candles, paper, backtest)

        self.assertEqual(journal.symbol, "BTC/USDT")
        self.assertEqual(journal.timeframe, "15m")
        self.assertGreater(journal.candle_count, 0)
        self.assertIn(journal.review_status, {"NEUTRAL", "PAPER_CANDIDATE", "OBSERVE_ONLY", "REVIEW_REQUIRED"})
        self.assertTrue(journal.notes)

    def test_save_daily_journal_json(self) -> None:
        journal = generate_daily_market_journal(uptrend_candles())
        with tempfile.TemporaryDirectory() as temp_dir:
            path = save_daily_market_journal(journal, Path(temp_dir))
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(path.name.endswith(".json"))
        self.assertEqual(payload["symbol"], "BTC/USDT")
        self.assertIn("review_status", payload)

    def test_negative_paper_result_requires_review(self) -> None:
        candles = uptrend_candles(60)
        candles.append(Candle("BTC/USDT", "15m", 61 * 900_000, 130, 131, 90, 101, 100))
        paper = run_paper_session(candles, metadata())

        journal = generate_daily_market_journal(candles, paper)

        self.assertEqual(journal.review_status, "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
