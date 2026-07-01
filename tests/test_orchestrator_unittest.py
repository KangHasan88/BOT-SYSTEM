from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.orchestrator import (
    ACTIONS,
    DatabasePanel,
    LiveEvidencePanel,
    TestnetDemoPanel,
    build_orchestrator_page,
    load_database_panel,
    load_health_summary,
    load_incident_panel,
    load_live_evidence_panel,
    load_orchestrator_status,
    load_report_browser,
    load_setup_wizard,
    load_testnet_demo_panel,
    recent_audit_events,
    run_orchestrator_action,
    update_kill_switch_from_web,
)
from trading_bot.observability import JsonlAuditLogger


class OrchestratorTest(unittest.TestCase):
    def test_page_has_safe_actions_and_no_live_order_button(self) -> None:
        status = load_orchestrator_status("config/bot.sample.toml")
        html = build_orchestrator_page(status)

        self.assertIn("Orchestrator Bot Trading", html)
        self.assertIn("fonts.bunny.net/css?family=inter", html)
        self.assertIn("board-header", html)
        self.assertIn("toolbar-group", html)
        self.assertIn("data-table", html)
        self.assertIn("Demo Data", html)
        self.assertIn("Evidence Campaign", html)
        self.assertIn("Testnet Demo", html)
        self.assertIn("Live Evidence", html)
        self.assertIn("Jalankan Siklus", html)
        self.assertIn("Sinkron BTC 15m", html)
        self.assertIn("Import DB", html)
        self.assertIn("Learning DB", html)
        self.assertIn("Limit candle", html)
        self.assertIn("Buat Dashboard", html)
        self.assertIn("Control Room Awam", html)
        self.assertIn("Cek Keamanan", html)
        self.assertIn("Cek Data Market", html)
        self.assertIn("Pantau P/L", html)
        self.assertIn("Review Go Live", html)
        self.assertIn("Setup Cepat", html)
        self.assertIn("Browser Laporan", html)
        self.assertIn("Database Lokal", html)
        self.assertIn("Demo/Testnet Monitoring", html)
        self.assertIn("Live Evidence Gate", html)
        self.assertIn("Kill Switch & Incident", html)
        self.assertIn("Tidak ada tombol live buy/sell/order", html)
        self.assertIn("Timeline Audit", html)
        self.assertNotIn("Buy", html)
        self.assertNotIn("Sell", html)

    def test_status_loader_reports_live_disabled(self) -> None:
        status = load_orchestrator_status("config/bot.sample.toml")

        self.assertFalse(status.live_enabled)
        self.assertIn("work", status.data_root)

    def test_health_summary_reports_key_domains(self) -> None:
        health = load_health_summary("config/bot.sample.toml")

        self.assertIn(health.data_status, {"OK", "BLOCKED", "MISSING"})
        self.assertIn(health.paper_status, {"ACTIVE", "NO_TRADES"})
        self.assertTrue(health.readiness_status)
        self.assertIn(health.safety_status, {"SAFE", "BLOCKED"})

    def test_setup_wizard_reports_first_run_steps(self) -> None:
        checks = load_setup_wizard("config/bot.sample.toml")
        by_name = {check.name: check for check in checks}

        self.assertIn("Config", by_name)
        self.assertIn("Live Guard", by_name)
        self.assertIn("Data Root", by_name)
        self.assertIn("Demo Data", by_name)
        self.assertIn("Security QA", by_name)
        self.assertIn("Dashboard", by_name)
        self.assertIn("Database", by_name)
        self.assertIn("First Run", by_name)
        self.assertEqual("PASS", by_name["Config"].status)
        self.assertEqual("PASS", by_name["Live Guard"].status)

    def test_report_browser_collects_research_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            _write_json(data_root / "backtests" / "BTC_USDT" / "15m" / "metrics.json", {"recommendation": "PAPER_CANDIDATE", "trade_count": 30})
            _write_json(data_root / "validation" / "walk_forward" / "BTC_USDT" / "15m.json", {"recommendation": "PASS", "total_test_trades": 30})
            _write_json(data_root / "reports" / "daily" / "BTC_USDT" / "15m" / "2026-06-30.json", {"review_status": "NEUTRAL", "paper_trade_count": 0})
            _write_json(data_root / "execution" / "testnet_demo" / "report.json", {"status": "PASSED", "orders": []})
            _write_json(data_root / "readiness" / "live_evidence.json", {"status": "INCOMPLETE", "completion_pct": 50})
            paper_path = data_root / "paper" / "BTC_USDT" / "trades.csv"
            paper_path.parent.mkdir(parents=True, exist_ok=True)
            paper_path.write_text("symbol,timeframe,net_pnl\nBTC/USDT,15m,1.2\n", encoding="utf-8")

            reports = load_report_browser(config_path)
            categories = {report.category for report in reports}

        self.assertIn("Backtest", categories)
        self.assertIn("Walk-Forward", categories)
        self.assertIn("Paper", categories)
        self.assertIn("Daily Journal", categories)
        self.assertIn("Testnet Demo", categories)
        self.assertIn("Readiness", categories)
        self.assertTrue(all(report.path for report in reports))

    def test_database_panel_renders_local_sqlite_summary(self) -> None:
        panel = DatabasePanel(
            db_path="work/market_data/bot.sqlite3",
            exists=True,
            size_bytes=4096,
            updated_at_utc="2026-06-30T00:00:00+00:00",
            total_rows=3,
            table_rows={"audit_events": 2, "orchestrator_activity": 1},
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, database=panel)

        self.assertIn("Database Lokal", html)
        self.assertIn("Total Rows", html)
        self.assertIn("audit_events", html)
        self.assertIn("orchestrator_activity", html)

    def test_database_panel_loader_reports_missing_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")

            panel = load_database_panel(config_path)

        self.assertFalse(panel.exists)
        self.assertEqual(0, panel.total_rows)
        self.assertIn("bot.sqlite3", panel.db_path)

    def test_testnet_demo_panel_renders_read_only_monitoring(self) -> None:
        panel = TestnetDemoPanel(
            report_path="work/market_data/execution/testnet_demo/report.json",
            exists=True,
            status="PASSED",
            environment="testnet",
            generated_at_utc="2026-07-01T00:00:00+00:00",
            order_count=1,
            live_guard_status="PASS",
            live_guard_reason="live rejected",
            orders=[
                {
                    "order_id": "testnet-1",
                    "symbol": "BTC/USDT",
                    "side": "buy",
                    "order_type": "market",
                    "quantity": 0.001,
                    "status": "FILLED",
                    "source": "testnet",
                }
            ],
            notes=["demo only"],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, testnet_demo=panel)

        self.assertIn("Demo/Testnet Monitoring", html)
        self.assertIn("Status Demo", html)
        self.assertIn("testnet-1", html)
        self.assertIn("live rejected", html)

    def test_testnet_demo_panel_loader_reports_missing_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")

            panel = load_testnet_demo_panel(config_path)

        self.assertFalse(panel.exists)
        self.assertEqual("MISSING", panel.status)
        self.assertIn("testnet_demo", panel.report_path)

    def test_live_evidence_panel_renders_blockers(self) -> None:
        panel = LiveEvidencePanel(
            report_path="work/market_data/readiness/live_evidence.json",
            exists=True,
            status="INCOMPLETE",
            completion_pct=46.15,
            generated_at_utc="2026-07-01T00:00:00+00:00",
            blocker_count=1,
            summary="7/13 evidence item(s) passed",
            blockers=["paper_trade_count: paper trades 15 below minimum 20"],
            items=[
                {
                    "name": "paper_trade_count",
                    "status": "BLOCKED",
                    "reason": "paper trades 15 below minimum 20",
                    "next_action": "continue paper campaign",
                }
            ],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, live_evidence=panel)

        self.assertIn("Live Evidence Gate", html)
        self.assertIn("46.15%", html)
        self.assertIn("paper_trade_count", html)
        self.assertIn("continue paper campaign", html)

    def test_live_evidence_panel_loader_reports_missing_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")

            panel = load_live_evidence_panel(config_path)

        self.assertFalse(panel.exists)
        self.assertEqual("MISSING", panel.status)
        self.assertIn("live_evidence.json", panel.report_path)

    def test_incident_panel_and_web_kill_switch_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")

            activated = update_kill_switch_from_web("activate", "operator drill", config_path)
            cleared = update_kill_switch_from_web("clear", "", config_path)
            panel = load_incident_panel(config_path)

        self.assertTrue(activated.kill_switch_active)
        self.assertEqual("operator drill", activated.kill_switch_reason)
        self.assertFalse(cleared.kill_switch_active)
        self.assertEqual("MISSING", panel.incident_status)

    def test_action_registry_has_only_safe_commands(self) -> None:
        self.assertIn("run_cycle", ACTIONS)
        self.assertIn("seed_demo_data", ACTIONS)
        self.assertIn("testnet_demo", ACTIONS)
        self.assertIn("live_evidence", ACTIONS)
        self.assertIn("evidence_campaign", ACTIONS)
        self.assertIn("import_runtime_db", ACTIONS)
        self.assertIn("db_learning_report", ACTIONS)
        self.assertIn("sync_btc_15m", ACTIONS)
        self.assertIn("sync_eth_15m", ACTIONS)
        self.assertIn("incident_drill", ACTIONS)
        rendered = " ".join(" ".join(command) for command in ACTIONS.values()).lower()

        self.assertNotIn("live-order", rendered)
        self.assertNotIn("buy", rendered)
        self.assertNotIn("sell", rendered)

    def test_run_action_writes_activity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "bot.toml"
            _write_config(config_path, root / "data")

            activity = run_orchestrator_action("validate_config", config_path=config_path, cwd=Path.cwd())
            activity_path = root / "data" / "orchestrator" / "activity.jsonl"

            self.assertEqual("SUCCESS", activity.status)
            self.assertTrue(activity_path.exists())
            self.assertIn("validate_config", activity_path.read_text(encoding="utf-8"))

    def test_run_action_rejects_while_lock_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            lock = data_root / "orchestrator" / "action.lock"
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text('{"action":"run_cycle"}', encoding="utf-8")

            with self.assertRaises(ValueError):
                run_orchestrator_action("validate_config", config_path=config_path, cwd=Path.cwd())

    def test_recent_audit_events_filters_level_symbol_and_timeframe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = JsonlAuditLogger(tmpdir)
            logger.write("cycle_start", "started", level="INFO")
            logger.write("pair_error", "bad candle", level="ERROR", symbol="BTC/USDT", timeframe="15m")
            logger.write("pair_error", "slow feed", level="ERROR", symbol="ETH/USDT", timeframe="15m")

            rows = recent_audit_events(tmpdir, level="ERROR", symbol="BTC/USDT", timeframe="15m")

        self.assertEqual(1, len(rows))
        self.assertEqual("pair_error", rows[0].event)
        self.assertEqual("BTC/USDT", rows[0].context["symbol"])

    def test_rejects_unsupported_action(self) -> None:
        with self.assertRaises(ValueError):
            run_orchestrator_action("place_live_order")


def _write_config(path: Path, data_root: Path) -> None:
    path.write_text(
        '[bot]\nmode = "paper"\nlive_enabled = false\napproved_live = false\ntimezone = "Asia/Jakarta"\n'
        '[market]\ntype = "crypto_spot"\nsymbols = ["BTC/USDT"]\ntimeframes = ["15m"]\n'
        '[data]\nroot = "'
        + str(data_root).replace("\\", "\\\\")
        + '"\nprovider = "binance_public"\n'
        '[risk]\nmax_open_positions = 1\n'
        '[sessions]\nentry_windows_wib = ["08:00-11:00"]\nalways_collect_data = true\n',
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
