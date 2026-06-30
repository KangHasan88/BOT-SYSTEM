from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_bot.qa import run_risk_guard_drill, save_risk_guard_drill_report
from trading_bot.safety import read_kill_switch


class RiskGuardDrillTest(unittest.TestCase):
    def test_risk_guard_drill_passes_all_required_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_risk_guard_drill(tmpdir, "BTC/USDT")

        self.assertEqual("PASSED", report.status)
        self.assertEqual(
            {
                "daily_stop",
                "monthly_drawdown",
                "profit_floor_stop",
                "daily_target_stop",
                "position_profit_lock",
                "kill_switch_roundtrip",
            },
            {check.name for check in report.checks},
        )
        self.assertTrue(all(check.status == "PASSED" for check in report.checks))

    def test_kill_switch_drill_does_not_activate_real_root_switch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_risk_guard_drill(root, "BTC/USDT")
            real_state = read_kill_switch(root)
            sandbox_state = read_kill_switch(root / "qa" / "risk_guard_drill" / "kill_switch_sandbox")

        self.assertFalse(real_state.active)
        self.assertFalse(sandbox_state.active)

    def test_saves_risk_guard_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = run_risk_guard_drill(root, "BTC/USDT")
            path = save_risk_guard_drill_report(report, root)

            self.assertTrue(path.exists())
            self.assertIn('"status": "PASSED"', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
