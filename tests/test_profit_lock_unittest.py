import unittest

from trading_bot.risk_manager import evaluate_daily_profit_lock, evaluate_position_lock


class ProfitLockTest(unittest.TestCase):
    def test_daily_lock_not_active_before_trigger(self) -> None:
        state = evaluate_daily_profit_lock(1_000.0, 1_003.0)

        self.assertEqual(state.status, "OPEN")
        self.assertFalse(state.lock_active)
        self.assertIsNone(state.floor_equity)

    def test_daily_lock_active_after_trigger(self) -> None:
        state = evaluate_daily_profit_lock(1_000.0, 1_006.0)

        self.assertEqual(state.status, "LOCK_ACTIVE")
        self.assertTrue(state.lock_active)
        self.assertAlmostEqual(state.floor_equity, 1_003.6)

    def test_daily_lock_stops_when_floor_hit(self) -> None:
        state = evaluate_daily_profit_lock(
            day_start_equity=1_000.0,
            current_equity=1_003.0,
            previous_high_watermark_equity=1_010.0,
        )

        self.assertEqual(state.status, "STOP_TRADING")
        self.assertAlmostEqual(state.floor_equity, 1_006.0)

    def test_daily_target_hit(self) -> None:
        state = evaluate_daily_profit_lock(1_000.0, 1_011.0)

        self.assertEqual(state.status, "DAILY_TARGET_HIT")

    def test_position_moves_stop_to_break_even_at_one_r(self) -> None:
        decision = evaluate_position_lock("buy", entry_price=100.0, stop_price=98.0, current_price=102.0)

        self.assertTrue(decision.should_update_stop)
        self.assertEqual(decision.new_stop_price, 100.0)

    def test_position_locks_profit_after_one_point_five_r(self) -> None:
        decision = evaluate_position_lock("buy", entry_price=100.0, stop_price=98.0, current_price=103.0)

        self.assertTrue(decision.should_update_stop)
        self.assertEqual(decision.new_stop_price, 100.5)

    def test_position_no_update_below_one_r(self) -> None:
        decision = evaluate_position_lock("buy", entry_price=100.0, stop_price=98.0, current_price=101.0)

        self.assertFalse(decision.should_update_stop)
        self.assertEqual(decision.new_stop_price, 98.0)


if __name__ == "__main__":
    unittest.main()
