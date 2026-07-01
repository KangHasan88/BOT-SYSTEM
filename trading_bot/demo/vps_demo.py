from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.config import BotConfig, load_config


@dataclass(frozen=True)
class VpsDemoCheck:
    name: str
    status: str
    reason: str
    next_action: str


@dataclass(frozen=True)
class VpsDemoReport:
    status: str
    generated_at_utc: str
    vps_config_path: str
    private_url: str
    tunnel_url: str
    live_locked: bool
    summary: str
    checks: list[VpsDemoCheck] = field(default_factory=list)


def build_vps_demo_report(
    runtime_config: BotConfig,
    vps_config_path: str | Path = "config/bot.vps.sample.toml",
    service_path: str | Path = "deploy/systemd/trading-bot-orchestrator.service",
    tunnel_script_path: str | Path = "scripts/start-vps-demo-tunnel.ps1",
    runbook_path: str | Path = "docs/private-vps-demo-access.md",
) -> VpsDemoReport:
    vps_config = load_config(Path(vps_config_path))
    service_text = _read_text(service_path)
    tunnel_text = _read_text(tunnel_script_path)
    runbook_text = _read_text(runbook_path)
    root = Path(runtime_config.data_root)
    local_demo = _read_json(root / "demo" / "local_demo.json") or {}
    paper_campaign = _read_json(root / "qa" / "paper_campaign" / "report.json") or {}
    live_locked = not runtime_config.live_enabled and not runtime_config.approved_live and not vps_config.live_enabled and not vps_config.approved_live

    checks = [
        VpsDemoCheck(
            "vps_config_paper_only",
            "PASS" if vps_config.mode == "paper" and not vps_config.live_enabled and not vps_config.approved_live else "FAIL",
            f"mode={vps_config.mode}, live_enabled={vps_config.live_enabled}, approved_live={vps_config.approved_live}",
            "Pastikan config/bot.vps.sample.toml tetap paper dan live disabled",
        ),
        VpsDemoCheck(
            "vps_data_root",
            "PASS" if str(vps_config.data_root) == "/var/lib/trading-bot/data" else "FAIL",
            str(vps_config.data_root),
            "Gunakan /var/lib/trading-bot/data untuk VPS paper data",
        ),
        VpsDemoCheck(
            "private_orchestrator_service",
            "PASS" if "serve-orchestrator" in service_text and "--host 127.0.0.1" in service_text and "--host 0.0.0.0" not in service_text else "FAIL",
            "service binds to 127.0.0.1" if "--host 127.0.0.1" in service_text else "service binding is not private",
            "Install deploy/systemd/trading-bot-orchestrator.service",
        ),
        VpsDemoCheck(
            "ssh_tunnel_script",
            "PASS" if "ssh -N -L" in tunnel_text and "127.0.0.1:$LocalPort" in tunnel_text else "FAIL",
            "tunnel script forwards local browser to VPS localhost",
            "Jalankan scripts/start-vps-demo-tunnel.ps1 dari laptop",
        ),
        VpsDemoCheck(
            "private_runbook",
            "PASS" if "Public Exposure Rejection" in runbook_text and "http://127.0.0.1:18000/" in runbook_text else "FAIL",
            "private VPS demo access runbook exists",
            "Baca docs/private-vps-demo-access.md",
        ),
        VpsDemoCheck(
            "local_demo_evidence",
            "PASS" if local_demo.get("status") == "READY_FOR_LOCAL_DEMO" else "TODO",
            f"local_demo={local_demo.get('status', 'missing')}",
            "Klik Local Demo sebelum VPS demo review",
        ),
        VpsDemoCheck(
            "paper_campaign_evidence",
            "PASS" if paper_campaign.get("status") in {"PAPER_CAMPAIGN_READY", "PAPER_CAMPAIGN_COLLECTING"} else "TODO",
            f"paper_campaign={paper_campaign.get('status', 'missing')}",
            "Klik Paper Campaign untuk refresh evidence paper",
        ),
        VpsDemoCheck(
            "live_lock",
            "PASS" if live_locked else "FAIL",
            "runtime and VPS configs keep live disabled" if live_locked else "one config enables live",
            "Pastikan live_enabled=false dan approved_live=false",
        ),
    ]
    failures = [check for check in checks if check.status == "FAIL"]
    todos = [check for check in checks if check.status == "TODO"]
    status = "READY_FOR_PRIVATE_VPS_DEMO" if not failures and not todos else "VPS_DEMO_PREP"
    return VpsDemoReport(
        status=status,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        vps_config_path=str(vps_config_path),
        private_url="http://127.0.0.1:8000/",
        tunnel_url="http://127.0.0.1:18000/",
        live_locked=live_locked,
        summary="private VPS paper demo path is ready" if status == "READY_FOR_PRIVATE_VPS_DEMO" else f"{len(failures) + len(todos)} VPS demo item(s) need attention",
        checks=checks,
    )


def save_vps_demo_report(report: VpsDemoReport, root: str | Path) -> Path:
    path = Path(root) / "demo" / "vps_demo.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _read_text(path: str | Path) -> str:
    target = Path(path)
    return target.read_text(encoding="utf-8") if target.exists() else ""


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
