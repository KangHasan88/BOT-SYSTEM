from pathlib import Path
import tempfile
import unittest

from trading_bot.data_collector import (
    CandleCsvStore,
    MarketContextCsvStore,
    MarketDataCollector,
    OrderBookSnapshot,
    SymbolMetadata,
    TickerSnapshot,
)


class FakeContextClient:
    def fetch_symbol_metadata(self, symbol: str) -> SymbolMetadata:
        return SymbolMetadata(
            symbol=symbol,
            base_asset="BTC",
            quote_asset="USDT",
            min_notional=5.0,
            price_precision=8,
            quantity_precision=8,
            taker_fee_pct=0.10,
            maker_fee_pct=0.10,
            source="fake",
        )

    def fetch_ticker_snapshot(self, symbol: str) -> TickerSnapshot:
        return TickerSnapshot(
            symbol=symbol,
            captured_at_ms=1_800_000,
            bid=100.0,
            ask=100.1,
            source="fake",
        )

    def fetch_order_book_snapshot(self, symbol: str) -> OrderBookSnapshot:
        return OrderBookSnapshot(
            symbol=symbol,
            captured_at_ms=1_800_000,
            best_bid=100.0,
            best_ask=100.1,
            bid_notional_top=1_000.0,
            ask_notional_top=500.0,
            source="fake",
        )


class MarketContextTest(unittest.TestCase):
    def test_ticker_spread_pct(self) -> None:
        ticker = TickerSnapshot("BTC/USDT", 1_800_000, 100.0, 100.1)

        self.assertAlmostEqual(ticker.spread, 0.1)
        self.assertAlmostEqual(ticker.spread_pct, 0.09995002498751028)

    def test_metadata_min_notional_guard(self) -> None:
        metadata = SymbolMetadata("BTC/USDT", "BTC", "USDT", 5.0, 8, 8, 0.10, 0.10)

        with self.assertRaises(ValueError):
            metadata.validate_order_notional(4.99)

        metadata.validate_order_notional(5.0)

    def test_context_capture_persists_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            collector = MarketDataCollector(
                store=CandleCsvStore(Path(temp_dir)),
                client=FakeContextClient(),
                context_store=MarketContextCsvStore(Path(temp_dir)),
            )

            metadata, ticker, order_book = collector.capture_market_context("BTC/USDT")

            self.assertEqual(metadata.min_notional, 5.0)
            self.assertGreater(ticker.spread_pct, 0)
            self.assertGreater(order_book.imbalance_ratio, 0)
            self.assertTrue((Path(temp_dir) / "metadata" / "BTC_USDT.csv").exists())
            self.assertTrue((Path(temp_dir) / "ticker" / "BTC_USDT.csv").exists())
            self.assertTrue((Path(temp_dir) / "order_book" / "BTC_USDT.csv").exists())


if __name__ == "__main__":
    unittest.main()
