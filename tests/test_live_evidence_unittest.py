from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.config import BotConfig
from trading_bot.readiness import evaluate_live_evidence, save_live_evidence_report


class LiveEvidenceTest(unittest.TestCase):
    def test_default_evidence_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = evaluate_live_evidence(_config(tmpdir))

        self.assertEqual("INCOMPLETE", report.status)
        self.assertLess(report.completion_pct, 100)
        self.assertTrue(report.blockers)
        self.assertTrue(any("paper_trade_count" in blocker for blocker in report.blockers))

    def test_complete_fixture_reaches_owner_review_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_complete_evidence(root)

            report = evaluate_live_evidence(_config(tmpdir, approved_live=True), min_paper_trades=2)

        self.assertEqual("COMPLETE_FOR_OWNER_REVIEW", report.status)
        self.assertEqual(100.0, report.completion_pct)
        self.assertEqual([], report.blockers)

    def test_save_live_evidence_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = evaluate_live_evidence(_config(tmpdir))
            path = save_live_evidence_report(report, tmpdir)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual("INCOMPLETE", payload["status"])
        self.assertIn("items", payload)


def _config(root: str, approved_live: bool = False) -> BotConfig:
    return BotConfig(
        mode="paper",
        live_enabled=False,
        approved_live=approved_live,
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


def _write_complete_evidence(root: Path) -> None:
    _write_json(root / "qa" / "security" / "report.json", {"status": "PASSED"})
    _write_json(root / "qa" / "data_quality_gate" / "BTC_USDT" / "15m" / "report.json", {"status": "PASSED"})
    _write_json(root / "backtests" / "BTC_USDT" / "15m" / "metrics.json", {"recommendation": "PAPER_CANDIDATE"})
    _write_json(root / "validation" / "walk_forward" / "BTC_USDT" / "15m.json", {"recommendation": "PAPER_CANDIDATE"})
    _write_json(root / "qa" / "paper_stability" / "BTC_USDT" / "15m" / "report.json", {"status": "PAPER_STABLE"})
    _write_json(root / "qa" / "risk_guard_drill" / "report.json", {"status": "PASSED"})
    _write_json(root / "qa" / "incident_drill" / "report.json", {"status": "PASSED"})
    _write_json(root / "execution" / "testnet_demo" / "report.json", {"status": "PASSED"})
    _write_json(root / "reports" / "learning" / "database_snapshot.json", {"rows": [{"symbol": "BTC/USDT"}]})
    _write_json(root / "readiness" / "live_readiness.json", {"status": "READY_FOR_MANUAL_REVIEW"})
    _write_json(root / "qa" / "live_go_no_go" / "report.json", {"decision": "GO_FOR_OWNER_REVIEW"})
    trade_path = root / "paper" / "BTC_USDT" / "15m" / "trades.csv"
    trade_path.parent.mkdir(parents=True, exist_ok=True)
    trade_path.write_text(
        "symbol,timeframe,entry_time_ms,exit_time_ms,entry_price,exit_price,quantity,gross_pnl,fees,net_pnl,exit_reason\n"
        "BTC/USDT,15m,1,2,100,101,0.1,0.1,0.01,0.09,take_profit\n"
        "BTC/USDT,15m,3,4,100,101,0.1,0.1,0.01,0.09,take_profit\n",
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
