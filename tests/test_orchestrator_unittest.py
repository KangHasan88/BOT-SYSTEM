from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.orchestrator import (
    ACTIONS,
    DatabasePanel,
    DemoWalkthroughStep,
    LiveEvidencePanel,
    LocalDemoPanel,
    PaperCampaignPanel,
    PnlPanel,
    PnlTradeRow,
    TestnetDemoPanel,
    VpsDemoPanel,
    build_orchestrator_page,
    load_database_panel,
    load_demo_walkthrough,
    load_health_summary,
    load_incident_panel,
    load_live_evidence_panel,
    load_local_demo_panel,
    load_orchestrator_status,
    load_paper_campaign_panel,
    load_pnl_panel,
    load_report_browser,
    load_setup_wizard,
    load_testnet_demo_panel,
    load_vps_demo_panel,
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
        self.assertIn("Demo Walkthrough", html)
        self.assertIn("Local Demo Readiness", html)
        self.assertIn("Private VPS Demo", html)
        self.assertIn("Paper Campaign", html)
        self.assertIn("Cek Keamanan", html)
        self.assertIn("Cek Data Market", html)
        self.assertIn("Pantau P/L", html)
        self.assertIn("P/L Visual Monitor", html)
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

    def test_pnl_panel_renders_equity_curve_and_latest_trade(self) -> None:
        pnl = PnlPanel(
            trade_count=2,
            win_rate_pct=50.0,
            net_pnl=12.5,
            initial_equity=1000.0,
            latest_equity=1012.5,
            equity_change_pct=1.25,
            best_trade_pnl=14.0,
            worst_trade_pnl=-1.5,
            latest_trade=PnlTradeRow("BTC/USDT", "15m", "2026-07-01T00:00+00:00", 100.0, 105.0, 14.0, "SESSION_END"),
            equity_points=[1000.0, 1004.0, 1012.5],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, pnl=pnl)

        self.assertIn("P/L Visual Monitor", html)
        self.assertIn("Realized P/L Demo", html)
        self.assertIn("Equity curve demo", html)
        self.assertIn("BTC/USDT", html)
        self.assertIn("SESSION_END", html)

    def test_demo_walkthrough_renders_numbered_beginner_steps(self) -> None:
        walkthrough = [
            DemoWalkthroughStep(1, "Buka Web Lokal", "PASS", "Buka halaman browser.", "Buka 127.0.0.1:8000", "Jika refused, start server."),
            DemoWalkthroughStep(2, "Cek Config", "TODO", "Pastikan config aman.", "Klik Validasi Config", "Ini belum trading."),
        ]
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, walkthrough=walkthrough)

        self.assertIn("Demo Walkthrough", html)
        self.assertIn("Buka Web Lokal", html)
        self.assertIn("Klik Validasi Config", html)
        self.assertIn("Ikuti urutan ini", html)

    def test_demo_walkthrough_loader_reports_safe_demo_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)

            steps = load_demo_walkthrough(config_path)

        self.assertEqual(6, len(steps))
        self.assertEqual("Buka Web Lokal", steps[0].title)
        self.assertEqual("PASS", steps[0].status)
        self.assertIn("Evidence", steps[3].title)
        self.assertIn("Real live tetap terkunci", steps[-1].help_text)

    def test_local_demo_panel_renders_readiness_summary(self) -> None:
        panel = LocalDemoPanel(
            report_path="work/market_data/demo/local_demo.json",
            exists=True,
            status="READY_FOR_LOCAL_DEMO",
            generated_at_utc="2026-07-01T00:00:00+00:00",
            candle_rows=180,
            paper_trades=4,
            report_count=8,
            live_locked=True,
            summary="local paper/demo path is ready",
            checks=[
                {
                    "name": "pnl_monitor",
                    "status": "PASS",
                    "reason": "P/L Visual Monitor has paper trades",
                    "next_action": "Lihat panel P/L Visual Monitor",
                }
            ],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, local_demo=panel)

        self.assertIn("Local Demo Readiness", html)
        self.assertIn("READY_FOR_LOCAL_DEMO", html)
        self.assertIn("LOCKED", html)
        self.assertIn("pnl_monitor", html)

    def test_local_demo_panel_loader_reads_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            _write_json(
                data_root / "demo" / "local_demo.json",
                {
                    "status": "READY_FOR_LOCAL_DEMO",
                    "generated_at_utc": "2026-07-01T00:00:00+00:00",
                    "candle_rows": 90,
                    "paper_trades": 2,
                    "report_count": 5,
                    "live_locked": True,
                    "summary": "ready",
                    "checks": [{"name": "config_safe", "status": "PASS"}],
                },
            )

            panel = load_local_demo_panel(config_path)

        self.assertTrue(panel.exists)
        self.assertEqual("READY_FOR_LOCAL_DEMO", panel.status)
        self.assertEqual(2, panel.paper_trades)

    def test_paper_campaign_panel_renders_campaign_progress(self) -> None:
        panel = PaperCampaignPanel(
            report_path="work/market_data/qa/paper_campaign/report.json",
            exists=True,
            status="PAPER_CAMPAIGN_COLLECTING",
            generated_at_utc="2026-07-01T00:00:00+00:00",
            completion_pct=71.43,
            pairs_checked=1,
            stable_pair_count=0,
            total_trade_count=19,
            total_net_pnl=12.5,
            summary="1 blocker(s) still collecting evidence",
            blockers=["BTC/USDT 15m: observed_days 7 < required 14"],
            pairs=[
                {
                    "symbol": "BTC/USDT",
                    "timeframe": "15m",
                    "status": "BLOCKED",
                    "observed_days": 7,
                    "target_days": 14,
                    "trade_count": 19,
                    "target_trades": 20,
                    "net_pnl": 12.5,
                    "blockers": ["observed_days 7 < required 14"],
                }
            ],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, paper_campaign=panel)

        self.assertIn("Paper Campaign", html)
        self.assertIn("71.43%", html)
        self.assertIn("BTC/USDT", html)
        self.assertIn("observed_days 7", html)

    def test_paper_campaign_panel_loader_reads_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            _write_json(
                data_root / "qa" / "paper_campaign" / "report.json",
                {
                    "status": "PAPER_CAMPAIGN_READY",
                    "generated_at_utc": "2026-07-01T00:00:00+00:00",
                    "completion_pct": 100.0,
                    "pairs_checked": 1,
                    "stable_pair_count": 1,
                    "total_trade_count": 20,
                    "total_net_pnl": 1.6,
                    "summary": "ready",
                    "blockers": [],
                    "pairs": [{"symbol": "BTC/USDT", "timeframe": "15m"}],
                },
            )

            panel = load_paper_campaign_panel(config_path)

        self.assertTrue(panel.exists)
        self.assertEqual("PAPER_CAMPAIGN_READY", panel.status)
        self.assertEqual(20, panel.total_trade_count)

    def test_vps_demo_panel_renders_private_access_summary(self) -> None:
        panel = VpsDemoPanel(
            report_path="work/market_data/demo/vps_demo.json",
            exists=True,
            status="READY_FOR_PRIVATE_VPS_DEMO",
            generated_at_utc="2026-07-01T00:00:00+00:00",
            vps_config_path="config/bot.vps.sample.toml",
            private_url="http://127.0.0.1:8000/",
            tunnel_url="http://127.0.0.1:18000/",
            live_locked=True,
            summary="private VPS paper demo path is ready",
            checks=[
                {
                    "name": "private_orchestrator_service",
                    "status": "PASS",
                    "reason": "service binds to 127.0.0.1",
                    "next_action": "Install service",
                }
            ],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, vps_demo=panel)

        self.assertIn("Private VPS Demo", html)
        self.assertIn("READY_FOR_PRIVATE_VPS_DEMO", html)
        self.assertIn("127.0.0.1:18000", html)
        self.assertIn("private_orchestrator_service", html)

    def test_vps_demo_panel_loader_reads_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            _write_json(
                data_root / "demo" / "vps_demo.json",
                {
                    "status": "READY_FOR_PRIVATE_VPS_DEMO",
                    "generated_at_utc": "2026-07-01T00:00:00+00:00",
                    "vps_config_path": "config/bot.vps.sample.toml",
                    "private_url": "http://127.0.0.1:8000/",
                    "tunnel_url": "http://127.0.0.1:18000/",
                    "live_locked": True,
                    "summary": "ready",
                    "checks": [{"name": "live_lock", "status": "PASS"}],
                },
            )

            panel = load_vps_demo_panel(config_path)

        self.assertTrue(panel.exists)
        self.assertEqual("READY_FOR_PRIVATE_VPS_DEMO", panel.status)
        self.assertTrue(panel.live_locked)

    def test_pnl_panel_loader_reads_paper_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            paper_root = data_root / "paper" / "BTC_USDT" / "15m"
            paper_root.mkdir(parents=True)
            (paper_root / "account.csv").write_text(
                "open_time_ms,equity,day_start_equity,month_start_equity,open_positions,consecutive_losses_today,trading_status,status_reason\n"
                "1717200000000,1000,1000,1000,0,0,OPEN,\n"
                "1717200900000,1008,1000,1000,0,0,OPEN,\n",
                encoding="utf-8",
            )
            (paper_root / "trades.csv").write_text(
                "symbol,timeframe,entry_time_ms,exit_time_ms,entry_price,exit_price,quantity,gross_pnl,fees,net_pnl,exit_reason\n"
                "BTC/USDT,15m,1717200000000,1717200900000,100,108,1,8,0,8,SESSION_END\n",
                encoding="utf-8",
            )

            panel = load_pnl_panel(config_path)

        self.assertEqual(1, panel.trade_count)
        self.assertEqual(100.0, panel.win_rate_pct)
        self.assertEqual(8.0, panel.net_pnl)
        self.assertEqual(1008.0, panel.latest_equity)

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
