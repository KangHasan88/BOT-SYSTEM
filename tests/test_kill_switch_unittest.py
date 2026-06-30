from pathlib import Path
import tempfile
import unittest

from trading_bot.config import BotConfig
from trading_bot.observability import read_audit_events
from trading_bot.ops import run_research_cycle
from trading_bot.safety import activate_kill_switch, clear_kill_switch, read_kill_switch


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


class KillSwitchTest(unittest.TestCase):
    def test_kill_switch_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = activate_kill_switch(Path(temp_dir), "manual drill")
            state = read_kill_switch(Path(temp_dir))
            clear_kill_switch(Path(temp_dir))
            cleared = read_kill_switch(Path(temp_dir))

        self.assertTrue(path.name.endswith(".json"))
        self.assertTrue(state.active)
        self.assertEqual(state.reason, "manual drill")
        self.assertFalse(cleared.active)

    def test_reason_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                activate_kill_switch(temp_dir, "")

    def test_cycle_blocks_when_kill_switch_active(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            activate_kill_switch(temp_dir, "manual drill")
            result = run_research_cycle(config(temp_dir), sync_latest=False)
            events = read_audit_events(temp_dir)

        self.assertEqual(result.timeframes_processed, 0)
        self.assertIn("cycle_blocked", {event.event for event in events})


if __name__ == "__main__":
    unittest.main()
