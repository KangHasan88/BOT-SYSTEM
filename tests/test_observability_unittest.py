from pathlib import Path
import tempfile
import unittest

from trading_bot.config import BotConfig
from trading_bot.observability import JsonlAuditLogger, read_audit_events
from trading_bot.ops import run_research_cycle


def config(root: str) -> BotConfig:
    return BotConfig(
        mode="paper",
        live_enabled=False,
        approved_live=False,
        symbols=("BTC/USDT",),
        market_type="crypto_spot",
        timeframes=("15m",),
        data_root=root,
        data_provider="binance_public",
        max_open_positions=1,
        daily_max_loss_pct=1.0,
        monthly_max_drawdown_pct=5.0,
        entry_windows_wib=("08:00-11:00",),
        always_collect_data=True,
    )


class ObservabilityTest(unittest.TestCase):
    def test_jsonl_audit_logger_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = JsonlAuditLogger(Path(temp_dir))
            logger.write("test_event", "hello", symbol="BTC/USDT")
            events = read_audit_events(Path(temp_dir))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, "test_event")
        self.assertEqual(events[0].context["symbol"], "BTC/USDT")

    def test_cycle_writes_audit_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_research_cycle(config(temp_dir), sync_latest=False)
            events = read_audit_events(temp_dir)

        self.assertEqual(result.timeframes_processed, 1)
        self.assertIn("cycle_start", {event.event for event in events})
        self.assertIn("pair_complete", {event.event for event in events})
        self.assertIn("cycle_complete", {event.event for event in events})


if __name__ == "__main__":
    unittest.main()
