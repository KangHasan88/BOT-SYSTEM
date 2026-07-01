from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PrivateVpsAccessTest(unittest.TestCase):
    def test_orchestrator_service_binds_to_localhost_only(self) -> None:
        service = (ROOT / "deploy" / "systemd" / "trading-bot-orchestrator.service").read_text(encoding="utf-8")

        self.assertIn("User=tradingbot", service)
        self.assertIn("serve-orchestrator", service)
        self.assertIn("--host 127.0.0.1", service)
        self.assertIn("--port 8000", service)
        self.assertNotIn("--host 0.0.0.0", service)

    def test_tunnel_script_uses_local_forward_without_credentials(self) -> None:
        script = (ROOT / "scripts" / "start-vps-demo-tunnel.ps1").read_text(encoding="utf-8")

        self.assertIn("ssh -N -L", script)
        self.assertIn("127.0.0.1:$LocalPort", script)
        self.assertIn("127.0.0.1:$RemotePort", script)
        self.assertNotIn("password", script.lower())
        self.assertNotIn("codex@123", script)

    def test_runbook_rejects_public_dashboard_exposure(self) -> None:
        runbook = (ROOT / "docs" / "private-vps-demo-access.md").read_text(encoding="utf-8")

        self.assertIn("SSH tunnel", runbook)
        self.assertIn("http://127.0.0.1:18000/", runbook)
        self.assertIn("Public Exposure Rejection", runbook)
        self.assertIn("`--host 0.0.0.0`", runbook)
        self.assertIn("Do not expose", (ROOT / "docs" / "vps-deployment.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
