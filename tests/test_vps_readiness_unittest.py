from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading_bot.qa import evaluate_vps_readiness, save_vps_readiness_report


ROOT = Path(__file__).resolve().parents[1]


class VpsReadinessReportTest(unittest.TestCase):
    def test_vps_readiness_passes_current_deployment_assets(self) -> None:
        report = evaluate_vps_readiness(
            ROOT / "config" / "bot.vps.sample.toml",
            ROOT / "deploy" / "systemd" / "trading-bot-cycle.service",
            ROOT / "deploy" / "systemd" / "trading-bot-cycle.timer",
            ROOT / "deploy" / "smoke-vps.sh",
        )

        self.assertEqual("PASSED", report.status)
        self.assertTrue(all(check.status == "PASSED" for check in report.checks))

    def test_vps_readiness_blocks_weak_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            service = root / "service"
            service.write_text(
                "[Service]\nUser=root\nExecStart=/opt/trading-bot/.venv/bin/python -m trading_bot.cli live\n",
                encoding="utf-8",
            )
            timer = root / "timer"
            timer.write_text("[Timer]\nOnUnitActiveSec=15min\nPersistent=true\nOnBootSec=2min\n", encoding="utf-8")
            smoke = root / "smoke.sh"
            smoke.write_text("validate-config\nrun-cycle\nbuild-dashboard\n", encoding="utf-8")

            report = evaluate_vps_readiness(ROOT / "config" / "bot.vps.sample.toml", service, timer, smoke)

        self.assertEqual("BLOCKED", report.status)
        failed = {check.name for check in report.checks if check.status == "FAILED"}
        self.assertIn("service_user", failed)
        self.assertIn("service_hardening", failed)
        self.assertIn("service_command", failed)

    def test_saves_vps_readiness_report(self) -> None:
        report = evaluate_vps_readiness(
            ROOT / "config" / "bot.vps.sample.toml",
            ROOT / "deploy" / "systemd" / "trading-bot-cycle.service",
            ROOT / "deploy" / "systemd" / "trading-bot-cycle.timer",
            ROOT / "deploy" / "smoke-vps.sh",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_vps_readiness_report(report, tmpdir)

            self.assertTrue(path.exists())
            self.assertIn('"status": "PASSED"', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
