from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.qa import evaluate_production_smoke, save_production_smoke_report


ROOT = Path(__file__).resolve().parents[1]


class ProductionSmokeTest(unittest.TestCase):
    def test_production_smoke_passes_with_existing_workspace_evidence(self) -> None:
        report = evaluate_production_smoke(
            ROOT / "config" / "bot.sample.toml",
            ROOT / "deploy" / "smoke-vps.sh",
            ROOT / "docs" / "vps-deployment.md",
        )

        self.assertEqual("PASSED", report.status)
        self.assertTrue(all(check.status == "PASSED" for check in report.checks))

    def test_production_smoke_blocks_missing_rollback_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = root / "bot.toml"
            config.write_text(
                '[bot]\nmode = "paper"\nlive_enabled = false\napproved_live = false\ntimezone = "Asia/Jakarta"\n'
                '[market]\ntype = "crypto_spot"\nsymbols = ["BTC/USDT"]\ntimeframes = ["15m"]\n'
                '[data]\nroot = "'
                + str(root).replace("\\", "\\\\")
                + '"\nprovider = "binance_public"\n'
                '[sessions]\nentry_windows_wib = ["08:00-11:00"]\nalways_collect_data = true\n',
                encoding="utf-8",
            )
            smoke = root / "smoke.sh"
            smoke.write_text("validate-config\nrun-cycle\nbuild-dashboard\n", encoding="utf-8")
            runbook = root / "runbook.md"
            runbook.write_text("rollback later\n", encoding="utf-8")
            _write_evidence(root)

            report = evaluate_production_smoke(config, smoke, runbook)

        self.assertEqual("BLOCKED", report.status)
        failed = {check.name for check in report.checks if check.status == "FAILED"}
        self.assertIn("rollback_timer_disable", failed)
        self.assertIn("rollback_restore_steps", failed)

    def test_saves_production_smoke_report(self) -> None:
        report = evaluate_production_smoke(
            ROOT / "config" / "bot.sample.toml",
            ROOT / "deploy" / "smoke-vps.sh",
            ROOT / "docs" / "vps-deployment.md",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_production_smoke_report(report, tmpdir)

            self.assertTrue(path.exists())
            self.assertIn('"status": "PASSED"', path.read_text(encoding="utf-8"))


def _write_evidence(root: Path) -> None:
    _write_json(root / "qa" / "security" / "report.json", {"status": "PASSED"})
    _write_json(root / "qa" / "risk_guard_drill" / "report.json", {"status": "PASSED"})
    _write_json(root / "qa" / "vps_readiness" / "report.json", {"status": "PASSED"})
    _write_json(root / "qa" / "incident_drill" / "report.json", {"status": "PASSED"})
    _write_json(root / "qa" / "live_go_no_go" / "report.json", {"decision": "NO_GO"})


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
