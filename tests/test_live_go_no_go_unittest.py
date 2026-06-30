from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.config import BotConfig
from trading_bot.qa import evaluate_live_go_no_go, save_live_go_no_go_report


class LiveGoNoGoTest(unittest.TestCase):
    def test_default_is_no_go_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = evaluate_live_go_no_go(_config(tmpdir), owner_approved=False)

        self.assertEqual("NO_GO", report.decision)
        self.assertTrue(any(item.name == "owner_approval" and item.status == "FAIL" for item in report.items))
        self.assertTrue(any(item.status == "FAIL" for item in report.items))

    def test_go_for_owner_review_when_all_evidence_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_evidence(root)
            report = evaluate_live_go_no_go(_config(tmpdir), owner_approved=True)

        self.assertEqual("GO_FOR_OWNER_REVIEW", report.decision)
        self.assertTrue(all(item.status == "PASS" for item in report.items))

    def test_blocks_when_paper_stability_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_evidence(root)
            _write_json(root / "qa" / "paper_stability" / "BTC_USDT" / "15m" / "report.json", {"status": "BLOCKED"})
            report = evaluate_live_go_no_go(_config(tmpdir), owner_approved=True)

        self.assertEqual("NO_GO", report.decision)
        paper = next(item for item in report.items if item.name == "paper_stability")
        self.assertEqual("FAIL", paper.status)

    def test_saves_go_no_go_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = evaluate_live_go_no_go(_config(tmpdir))
            path = save_live_go_no_go_report(report, tmpdir)

            self.assertTrue(path.exists())
            self.assertIn('"decision": "NO_GO"', path.read_text(encoding="utf-8"))


def _config(root: str) -> BotConfig:
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


def _write_evidence(root: Path) -> None:
    _write_json(root / "qa" / "security" / "report.json", {"status": "PASSED"})
    _write_json(root / "qa" / "risk_guard_drill" / "report.json", {"status": "PASSED"})
    _write_json(root / "qa" / "vps_readiness" / "report.json", {"status": "PASSED"})
    _write_json(root / "qa" / "incident_drill" / "report.json", {"status": "PASSED"})
    _write_json(root / "qa" / "paper_stability" / "BTC_USDT" / "15m" / "report.json", {"status": "PAPER_STABLE"})
    _write_json(root / "qa" / "data_quality_gate" / "BTC_USDT" / "15m" / "report.json", {"status": "PASSED"})
    _write_json(root / "readiness" / "live_readiness.json", {"status": "READY_FOR_MANUAL_REVIEW"})


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
