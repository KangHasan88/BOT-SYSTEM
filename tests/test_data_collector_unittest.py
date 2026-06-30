from pathlib import Path
import tempfile
import unittest

from trading_bot.data_collector import Candle, CandleCsvStore, MarketDataCollector, find_gaps


class FakeClient:
    def __init__(self, candles: list[Candle]) -> None:
        self.candles = candles

    def fetch_klines(self, symbol: str, timeframe: str, limit: int = 500) -> list[Candle]:
        return self.candles[:limit]


class FakeBackfillClient:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
        start_time_ms: int | None = None,
    ) -> list[Candle]:
        self.calls.append(start_time_ms or 0)
        if len(self.calls) > 2:
            return []
        base = start_time_ms or 900_000
        return [
            Candle(symbol, timeframe, base, 100, 101, 99, 100, 1),
            Candle(symbol, timeframe, base + 900_000, 101, 102, 100, 101, 1),
        ]


class DataCollectorTest(unittest.TestCase):
    def test_store_dedups_and_sorts_candles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = CandleCsvStore(Path(temp_dir))
            candles = [
                Candle("BTC/USDT", "15m", 1_800_000, 101, 102, 100, 101, 10),
                Candle("BTC/USDT", "15m", 900_000, 100, 101, 99, 100, 9),
                Candle("BTC/USDT", "15m", 900_000, 100, 101, 99, 100.5, 11),
            ]

            inserted = store.upsert_many(candles)
            loaded = store.load("BTC/USDT", "15m")

            self.assertEqual(inserted, 2)
            self.assertEqual([item.open_time_ms for item in loaded], [900_000, 1_800_000])
            self.assertEqual(loaded[0].close, 100.5)

    def test_gap_detector_finds_missing_candle(self) -> None:
        candles = [
            Candle("BTC/USDT", "15m", 0 + 900_000, 100, 101, 99, 100, 1),
            Candle("BTC/USDT", "15m", 0 + 2_700_000, 102, 103, 101, 102, 1),
        ]

        gaps = find_gaps(candles)

        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].missing_open_time_ms, 1_800_000)

    def test_collector_syncs_with_fake_client(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            candles = [
                Candle("ETH/USDT", "1h", 3_600_000, 100, 101, 99, 100, 1),
                Candle("ETH/USDT", "1h", 7_200_000, 101, 102, 100, 101, 1),
            ]
            collector = MarketDataCollector(
                CandleCsvStore(Path(temp_dir)),
                FakeClient(candles),
            )

            result = collector.sync_latest("ETH/USDT", "1h", limit=10)

            self.assertEqual(result.fetched, 2)
            self.assertEqual(result.inserted_or_updated, 2)
            self.assertEqual(result.total_after_sync, 2)

    def test_backfill_batches_and_quality_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            collector = MarketDataCollector(
                CandleCsvStore(Path(temp_dir)),
                FakeBackfillClient(),
            )

            result = collector.backfill("BTC/USDT", "15m", start_time_ms=900_000, batches=2, limit=2)
            report = collector.quality_report("BTC/USDT", "15m")

            self.assertEqual(result.fetched, 4)
            self.assertEqual(result.total_after_sync, 4)
            self.assertEqual(report.candle_count, 4)
            self.assertEqual(report.gap_count, 0)
            self.assertEqual(report.duplicate_count, 0)
            self.assertEqual(len(report.dataset_id), 16)


if __name__ == "__main__":
    unittest.main()
