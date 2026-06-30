from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_bot.observability import read_audit_events
from trading_bot.qa import run_incident_drill, save_incident_drill_report


class IncidentDrillTest(unittest.TestCase):
    def test_incident_drill_passes_all_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_incident_drill(tmpdir, "BTC/USDT")
            events = {event.event for event in read_audit_events(tmpdir)}
            alert_files = list((Path(tmpdir) / "alerts" / "outbox").glob("*.json"))

        self.assertEqual("PASSED", report.status)
        self.assertEqual(
            {"exchange_api_down", "network_down", "bot_crash"},
            {scenario.name for scenario in report.scenarios},
        )
        self.assertIn("incident_exchange_api_down", events)
        self.assertIn("incident_network_down", events)
        self.assertIn("incident_bot_crash", events)
        self.assertGreaterEqual(len(alert_files), 2)

    def test_incident_drill_safe_responses_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_incident_drill(tmpdir, "BTC/USDT")

        responses = {scenario.name: scenario.safe_response for scenario in report.scenarios}
        self.assertEqual("skip sync and block new entries", responses["exchange_api_down"])
        self.assertEqual("do not trade on stale data", responses["network_down"])
        self.assertEqual("require operator review before restart", responses["bot_crash"])

    def test_saves_incident_drill_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_incident_drill(tmpdir, "BTC/USDT")
            path = save_incident_drill_report(report, tmpdir)

            self.assertTrue(path.exists())
            self.assertIn('"status": "PASSED"', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
