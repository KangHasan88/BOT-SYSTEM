from datetime import datetime, timezone
import unittest

from trading_bot.scheduler import is_entry_allowed_at_ms, is_time_in_windows, parse_session_window


def ms_utc(year: int, month: int, day: int, hour: int, minute: int) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp() * 1000)


class SchedulerTest(unittest.TestCase):
    def test_parse_session_window(self) -> None:
        start, end = parse_session_window("08:00-11:00")

        self.assertEqual(start.hour, 8)
        self.assertEqual(end.hour, 11)

    def test_entry_allowed_inside_wib_window(self) -> None:
        decision = is_entry_allowed_at_ms(
            ms_utc(2026, 6, 29, 1, 30),
            ("08:00-11:00", "19:00-23:30"),
        )

        self.assertTrue(decision.allowed)
        self.assertIn("WIB", decision.local_time)

    def test_entry_rejected_outside_wib_window(self) -> None:
        decision = is_entry_allowed_at_ms(
            ms_utc(2026, 6, 29, 5, 0),
            ("08:00-11:00", "19:00-23:30"),
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "outside configured entry window")

    def test_overnight_window(self) -> None:
        self.assertTrue(is_time_in_windows(parse_session_window("23:00-02:00")[0], ("23:00-02:00",)))


if __name__ == "__main__":
    unittest.main()
