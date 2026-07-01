from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_bot.execution import run_testnet_demo_report, save_testnet_demo_report


class TestnetDemoReportTest(unittest.TestCase):
    def test_testnet_demo_report_places_and_cancels_safe_orders(self) -> None:
        report = run_testnet_demo_report("testnet")

        statuses = [order.status for order in report.orders]

        self.assertEqual("PASSED", report.status)
        self.assertEqual("testnet", report.environment)
        self.assertEqual(["FILLED", "OPEN", "CANCELED"], statuses)
        self.assertEqual("PASS", report.live_guard_status)
        self.assertTrue(all(order.source == "testnet" for order in report.orders))

    def test_testnet_demo_rejects_live_environment(self) -> None:
        with self.assertRaises(ValueError):
            run_testnet_demo_report("live")

    def test_save_testnet_demo_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_testnet_demo_report("sandbox")
            path = save_testnet_demo_report(report, tmpdir)

            self.assertTrue(path.exists())
            self.assertIn("testnet_demo", str(path))
            self.assertIn("sandbox", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
