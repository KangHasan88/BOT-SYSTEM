from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_bot.orchestrator import (
    ACTIONS,
    DatabasePanel,
    DemoWalkthroughStep,
    ExperimentScoreboardPanel,
    FundamentalPanel,
    HumanFeedbackPanel,
    LearningDashboardPanel,
    LiveEvidencePanel,
    LocalDemoPanel,
    PaperCampaignPanel,
    PatternMemoryPanel,
    SkillLoopPanel,
    PnlPanel,
    PnlTradeRow,
    TestnetDemoPanel,
    VpsDemoPanel,
    build_orchestrator_page,
    load_database_panel,
    load_demo_walkthrough,
    load_experiment_scoreboard_panel,
    load_fundamental_panel,
    load_glossary_entries,
    load_health_summary,
    load_human_feedback_panel,
    load_incident_panel,
    load_learning_dashboard_panel,
    load_live_evidence_panel,
    load_local_demo_panel,
    load_orchestrator_status,
    load_paper_campaign_panel,
    load_pattern_memory_panel,
    load_skill_loop_panel,
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
        self.assertIn("Mulai di Sini", html)
        self.assertIn("Start Web Demo", html)
        self.assertIn("start-bot-web.cmd", html)
        self.assertIn("start-bot-watchdog.cmd", html)
        self.assertIn("Control Room Awam", html)
        self.assertIn("Demo Walkthrough", html)
        self.assertIn("Local Demo Readiness", html)
        self.assertIn("Private VPS Demo", html)
        self.assertIn("Paper Campaign", html)
        self.assertIn("Skill Loop", html)
        self.assertIn("Pattern Memory", html)
        self.assertIn("Learning Dashboard", html)
        self.assertIn("Human Feedback", html)
        self.assertIn("Fundamental/Event Lane", html)
        self.assertIn("Experiment Scoreboard", html)
        self.assertIn("Kamus Awam", html)
        self.assertIn("Evidence Score", html)
        self.assertIn("Arti Awam", html)
        self.assertIn("title=\"Cek mode bot, live lock, dan simbol tanpa melakukan order.\"", html)
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

    def test_glossary_entries_cover_beginner_terms(self) -> None:
        entries = load_glossary_entries()
        terms = {entry.term for entry in entries}

        self.assertIn("Paper/Demo", terms)
        self.assertIn("P/L", terms)
        self.assertIn("Evidence Score", terms)
        self.assertTrue(all(entry.plain_meaning for entry in entries))
        self.assertTrue(all(entry.related_action for entry in entries))

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
        self.assertIn("Kesimpulan Awam", html)
        self.assertIn("Profit Demo", html)
        self.assertIn("Realized P/L Demo", html)
        self.assertIn("Equity curve demo", html)
        self.assertIn("BTC/USDT", html)
        self.assertIn("SESSION_END", html)

    def test_pnl_panel_explains_mixed_profit_and_equity_drawdown(self) -> None:
        pnl = PnlPanel(
            trade_count=19,
            win_rate_pct=63.16,
            net_pnl=187.61379981,
            initial_equity=6000.0,
            latest_equity=5989.6706342,
            equity_change_pct=-0.17,
            best_trade_pnl=36.34904994,
            worst_trade_pnl=-3.04754787,
            latest_trade=PnlTradeRow("ETH/USDT", "4h", "2024-08-23T09:33+00:00", 3827.62, 4234.67, 27.33721622, "SESSION_END"),
            equity_points=[6000.0, 5989.6706342],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, pnl=pnl)

        self.assertIn("Campuran / Perlu Review", html)
        self.assertIn("saldo demo terakhir turun", html)
        self.assertIn("5989.67 - 6000.00 = -10.33 USDT", html)
        self.assertIn("USDT, patokan dollar stablecoin", html)
        self.assertIn('class="metric-note delta-danger"', html)
        self.assertNotIn('&lt;span class=&quot;small&quot;&gt;', html)
        self.assertIn("Aksi berikut", html)
        self.assertIn("Equity Change", html)

    def test_pnl_panel_colors_positive_equity_delta_green(self) -> None:
        pnl = PnlPanel(
            trade_count=3,
            win_rate_pct=66.67,
            net_pnl=25.0,
            initial_equity=1000.0,
            latest_equity=1025.0,
            equity_change_pct=2.5,
            best_trade_pnl=20.0,
            worst_trade_pnl=-2.0,
            latest_trade=PnlTradeRow("BTC/USDT", "15m", "2026-07-01T00:00+00:00", 100.0, 105.0, 20.0, "TP"),
            equity_points=[1000.0, 1025.0],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, pnl=pnl)

        self.assertIn("1025.00 - 1000.00 = +25.00 USDT", html)
        self.assertIn('class="metric-note delta-ok"', html)

    def test_demo_walkthrough_renders_numbered_beginner_steps(self) -> None:
        walkthrough = [
            DemoWalkthroughStep(1, "Buka Web Lokal", "PASS", "Buka halaman browser.", "Buka 127.0.0.1:8000", "Jika refused, start server."),
            DemoWalkthroughStep(2, "Cek Config", "TODO", "Pastikan config aman.", "Klik Validasi Config", "Ini belum trading."),
            DemoWalkthroughStep(3, "Isi Data Demo", "TODO", "Siapkan data demo.", "Klik Demo Data", "Ini belum live."),
            DemoWalkthroughStep(4, "Jalankan Evidence", "TODO", "Refresh evidence.", "Klik Evidence Campaign", "Ini cek bukti."),
            DemoWalkthroughStep(5, "Pantau P/L", "TODO", "Pantau P/L demo.", "Lihat P/L Visual Monitor", "Ini saldo simulasi."),
            DemoWalkthroughStep(6, "Review Go Live", "TODO", "Review blocker.", "Klik Live Evidence", "Live tetap terkunci."),
        ]
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, walkthrough=walkthrough)

        self.assertIn("Demo Walkthrough", html)
        self.assertIn("Buka Web Lokal", html)
        self.assertIn('data-scroll="mulai-di-sini"', html)
        self.assertIn('data-action="validate_config"', html)
        self.assertIn('data-action="seed_demo_data"', html)
        self.assertIn('data-scroll="pnl-monitor"', html)
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

    def test_skill_loop_panel_renders_learning_summary(self) -> None:
        panel = SkillLoopPanel(
            report_path="work/market_data/reports/learning/skill_loop.json",
            exists=True,
            status="SKILL_LOOP_ACTIVE",
            generated_at_utc="2026-07-01T00:00:00+00:00",
            candle_rows=3000,
            paper_trades=19,
            paper_net_pnl=187.6,
            learning_rows=6,
            evidence_completion_pct=53.0,
            paper_campaign_status="PAPER_CAMPAIGN_COLLECTING",
            summary="skill loop active",
            guardrail="Research only. No live orders.",
            experiment_candidates=["Review pattern note: WATCH_VOLUME_SPIKE"],
            steps=[{"name": "capture_data", "status": "PASS", "metric": "candles=3000", "finding": "market data tersedia", "next_action": ""}],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, skill_loop=panel)

        self.assertIn("Skill Loop", html)
        self.assertIn("SKILL_LOOP_ACTIVE", html)
        self.assertIn("WATCH_VOLUME_SPIKE", html)
        self.assertIn("No live orders", html)

    def test_skill_loop_panel_loader_reads_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            _write_json(
                data_root / "reports" / "learning" / "skill_loop.json",
                {
                    "status": "SKILL_LOOP_ACTIVE",
                    "generated_at_utc": "2026-07-01T00:00:00+00:00",
                    "candle_rows": 80,
                    "paper_trades": 1,
                    "paper_net_pnl": 1.0,
                    "learning_rows": 1,
                    "evidence_completion_pct": 50.0,
                    "paper_campaign_status": "PAPER_CAMPAIGN_COLLECTING",
                    "summary": "active",
                    "guardrail": "Research only. No live orders.",
                    "experiment_candidates": ["review"],
                    "steps": [{"name": "capture_data", "status": "PASS"}],
                },
            )

            panel = load_skill_loop_panel(config_path)

        self.assertTrue(panel.exists)
        self.assertEqual("SKILL_LOOP_ACTIVE", panel.status)
        self.assertEqual(1, panel.learning_rows)

    def test_pattern_memory_panel_renders_outcome_summary(self) -> None:
        panel = PatternMemoryPanel(
            report_path="work/market_data/reports/learning/pattern_memory.json",
            exists=True,
            status="PATTERN_MEMORY_ACTIVE",
            generated_at_utc="2026-07-01T00:00:00+00:00",
            row_count=1,
            total_trades=2,
            total_labels=1,
            summary="pattern memory active",
            guardrail="Review only. No live orders.",
            rows=[
                {
                    "symbol": "BTC/USDT",
                    "timeframe": "15m",
                    "observation": "WATCH_VOLUME_SPIKE",
                    "outcome_grade": "NEEDS_MORE_TRADES",
                    "trade_count": 2,
                    "win_rate_pct": 50.0,
                    "total_net_pnl": 0.08,
                    "labels": ["good_retest_after_sweep"],
                    "next_action": "Lanjutkan paper campaign",
                }
            ],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, pattern_memory=panel)

        self.assertIn("Pattern Memory", html)
        self.assertIn("PATTERN_MEMORY_ACTIVE", html)
        self.assertIn("WATCH_VOLUME_SPIKE", html)
        self.assertIn("good_retest_after_sweep", html)

    def test_pattern_memory_panel_loader_reads_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            _write_json(
                data_root / "reports" / "learning" / "pattern_memory.json",
                {
                    "status": "PATTERN_MEMORY_ACTIVE",
                    "generated_at_utc": "2026-07-01T00:00:00+00:00",
                    "row_count": 1,
                    "total_trades": 2,
                    "total_labels": 1,
                    "summary": "active",
                    "guardrail": "Review only. No live orders.",
                    "rows": [{"symbol": "BTC/USDT", "timeframe": "15m", "outcome_grade": "NEEDS_MORE_TRADES"}],
                },
            )

            panel = load_pattern_memory_panel(config_path)

        self.assertTrue(panel.exists)
        self.assertEqual("PATTERN_MEMORY_ACTIVE", panel.status)
        self.assertEqual(1, panel.total_labels)

    def test_learning_dashboard_panel_renders_evidence_score(self) -> None:
        panel = LearningDashboardPanel(
            report_path="work/market_data/reports/learning/learning_dashboard.json",
            exists=True,
            status="LEARNING_DASHBOARD_ACTIVE",
            generated_at_utc="2026-07-01T00:00:00+00:00",
            trend_count=1,
            promising_count=0,
            weak_count=0,
            volume_spike_count=1,
            average_evidence_score=19.0,
            live_evidence_completion_pct=50.0,
            paper_campaign_completion_pct=40.0,
            summary="active",
            guardrail="Read-only research. No live execution.",
            trends=[
                {
                    "symbol": "BTC/USDT",
                    "timeframe": "15m",
                    "observation": "WATCH_VOLUME_SPIKE",
                    "outcome_grade": "NEEDS_MORE_TRADES",
                    "status": "BUTUH PAPER",
                    "evidence_score": 19.0,
                    "volume_spike": True,
                    "trade_count": 3,
                    "win_rate_pct": 66.67,
                    "total_net_pnl": 1.2,
                    "next_action": "Lanjut paper campaign",
                }
            ],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, learning_dashboard=panel)

        self.assertIn("Learning Dashboard", html)
        self.assertIn("LEARNING_DASHBOARD_ACTIVE", html)
        self.assertIn("WATCH_VOLUME_SPIKE", html)
        self.assertIn("BUTUH PAPER", html)

    def test_learning_dashboard_panel_loader_reads_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            _write_json(
                data_root / "reports" / "learning" / "learning_dashboard.json",
                {
                    "status": "LEARNING_DASHBOARD_ACTIVE",
                    "generated_at_utc": "2026-07-01T00:00:00+00:00",
                    "trend_count": 1,
                    "promising_count": 0,
                    "weak_count": 0,
                    "volume_spike_count": 1,
                    "average_evidence_score": 19.0,
                    "live_evidence_completion_pct": 50.0,
                    "paper_campaign_completion_pct": 40.0,
                    "summary": "active",
                    "guardrail": "Read-only research. No live execution.",
                    "trends": [{"symbol": "BTC/USDT", "status": "BUTUH PAPER"}],
                },
            )

            panel = load_learning_dashboard_panel(config_path)

        self.assertTrue(panel.exists)
        self.assertEqual("LEARNING_DASHBOARD_ACTIVE", panel.status)
        self.assertEqual(1, panel.volume_spike_count)

    def test_human_feedback_panel_renders_lessons(self) -> None:
        panel = HumanFeedbackPanel(
            report_path="work/market_data/reports/learning/human_feedback.json",
            exists=True,
            status="HUMAN_FEEDBACK_ACTIVE",
            generated_at_utc="2026-07-01T00:00:00+00:00",
            label_path="work/market_data/reports/learning/manual_labels.json",
            total_labels=1,
            pairs_labeled=1,
            top_label="entry_telat",
            summary="1 feedback label terbaca",
            guardrail="Human feedback can update lessons, but must never place live orders.",
            allowed_labels=["entry_telat", "false_signal"],
            label_counts={"entry_telat": 1},
            recent_labels=[
                {
                    "symbol": "BTC/USDT",
                    "timeframe": "15m",
                    "label": "entry_telat",
                    "note": "entry terlalu jauh dari trigger",
                    "reviewer": "hasan",
                    "created_at_utc": "2026-07-01T00:00:00+00:00",
                }
            ],
            lessons=[
                {
                    "label": "entry_telat",
                    "count": 1,
                    "lesson": "entry sering terlambat",
                    "next_action": "Review candle sebelum entry",
                }
            ],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, human_feedback=panel)

        self.assertIn("Human Feedback", html)
        self.assertIn("HUMAN_FEEDBACK_ACTIVE", html)
        self.assertIn("entry_telat", html)
        self.assertIn("Review candle sebelum entry", html)

    def test_human_feedback_panel_loader_reads_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            _write_json(
                data_root / "reports" / "learning" / "human_feedback.json",
                {
                    "status": "HUMAN_FEEDBACK_ACTIVE",
                    "generated_at_utc": "2026-07-01T00:00:00+00:00",
                    "label_path": "manual_labels.json",
                    "total_labels": 1,
                    "pairs_labeled": 1,
                    "top_label": "entry_telat",
                    "summary": "active",
                    "guardrail": "No live orders.",
                    "allowed_labels": ["entry_telat"],
                    "label_counts": {"entry_telat": 1},
                    "recent_labels": [{"symbol": "BTC/USDT", "label": "entry_telat"}],
                    "lessons": [{"label": "entry_telat", "count": 1}],
                },
            )

            panel = load_human_feedback_panel(config_path)

        self.assertTrue(panel.exists)
        self.assertEqual("HUMAN_FEEDBACK_ACTIVE", panel.status)
        self.assertEqual(1, panel.total_labels)

    def test_fundamental_panel_renders_risk_colors(self) -> None:
        panel = FundamentalPanel(
            report_path="work/market_data/reports/fundamental/report.json",
            exists=True,
            status="FUNDAMENTAL_BLOCK",
            generated_at_utc="2026-07-02T00:00:00+00:00",
            event_path="work/market_data/reports/fundamental/events.json",
            total_events=1,
            high_or_block_events=1,
            top_risk="BLOCK",
            color="red",
            summary="1 event fundamental terbaca",
            guardrail="Fundamental lane is review-only. No live orders.",
            risk_counts={"BLOCK": 1},
            category_counts={"exchange": 1},
            events=[
                {
                    "symbol": "BTC/USDT",
                    "category": "exchange",
                    "risk": "BLOCK",
                    "title": "Exchange maintenance",
                    "source": "manual",
                    "note": "pause",
                    "event_time_utc": "2026-07-02T00:00:00+00:00",
                }
            ],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, fundamental=panel)

        self.assertIn("Fundamental/Event Lane", html)
        self.assertIn("FUNDAMENTAL_BLOCK", html)
        self.assertIn("BLOCK / red", html)
        self.assertIn("Exchange maintenance", html)

    def test_fundamental_panel_loader_reads_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            _write_json(
                data_root / "reports" / "fundamental" / "report.json",
                {
                    "status": "FUNDAMENTAL_HIGH_RISK",
                    "generated_at_utc": "2026-07-02T00:00:00+00:00",
                    "event_path": "events.json",
                    "total_events": 1,
                    "high_or_block_events": 1,
                    "top_risk": "HIGH",
                    "color": "orange",
                    "summary": "risk",
                    "guardrail": "No live orders.",
                    "risk_counts": {"HIGH": 1},
                    "category_counts": {"macro": 1},
                    "events": [{"symbol": "BTC/USDT", "risk": "HIGH"}],
                },
            )

            panel = load_fundamental_panel(config_path)

        self.assertTrue(panel.exists)
        self.assertEqual("FUNDAMENTAL_HIGH_RISK", panel.status)
        self.assertEqual("orange", panel.color)

    def test_experiment_scoreboard_panel_renders_rows(self) -> None:
        panel = ExperimentScoreboardPanel(
            report_path="work/market_data/reports/learning/experiment_scoreboard.json",
            exists=True,
            status="EXPERIMENT_SCOREBOARD_ACTIVE",
            generated_at_utc="2026-07-02T00:00:00+00:00",
            registry_path="work/market_data/reports/learning/strategy_experiments.json",
            experiment_count=1,
            top_strategy="volume_spike_retest v1",
            summary="1 eksperimen tercatat",
            guardrail="Experiment registry is review-only. No live orders.",
            rows=[
                {
                    "strategy_id": "volume_spike_retest",
                    "version": "v1",
                    "status": "PAPER",
                    "total_score": 70,
                    "recommendation": "PAPER_CANDIDATE",
                    "hypothesis": "volume spike improves entry",
                    "source": "manual",
                }
            ],
        )
        status = load_orchestrator_status("config/bot.sample.toml")

        html = build_orchestrator_page(status, experiment_scoreboard=panel)

        self.assertIn("Experiment Scoreboard", html)
        self.assertIn("volume_spike_retest", html)
        self.assertIn("PAPER_CANDIDATE", html)

    def test_experiment_scoreboard_panel_loader_reads_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_root = root / "data"
            config_path = root / "bot.toml"
            _write_config(config_path, data_root)
            _write_json(
                data_root / "reports" / "learning" / "experiment_scoreboard.json",
                {
                    "status": "EXPERIMENT_SCOREBOARD_ACTIVE",
                    "generated_at_utc": "2026-07-02T00:00:00+00:00",
                    "registry_path": "strategy_experiments.json",
                    "experiment_count": 1,
                    "top_strategy": "x v1",
                    "summary": "active",
                    "guardrail": "No live orders.",
                    "rows": [{"strategy_id": "x", "version": "v1"}],
                },
            )

            panel = load_experiment_scoreboard_panel(config_path)

        self.assertTrue(panel.exists)
        self.assertEqual("EXPERIMENT_SCOREBOARD_ACTIVE", panel.status)
        self.assertEqual(1, panel.experiment_count)

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
        self.assertIn("fundamental", ACTIONS)
        self.assertIn("experiment_scoreboard", ACTIONS)
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
