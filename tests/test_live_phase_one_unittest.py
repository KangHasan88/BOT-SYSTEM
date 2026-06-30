import unittest

from trading_bot.live import LivePhaseOneConfig, build_live_phase_one_plan
from trading_bot.readiness import ReadinessCheck, ReadinessReport


def readiness(status: str) -> ReadinessReport:
    return ReadinessReport(
        status=status,
        checks=[ReadinessCheck("dummy", "PASS", "ok")],
        summary="test",
    )


class LivePhaseOneTest(unittest.TestCase):
    def test_blocked_when_readiness_not_passed(self) -> None:
        plan = build_live_phase_one_plan(readiness("BLOCKED"), LivePhaseOneConfig(capital_idr=1_000_000))

        self.assertEqual(plan.status, "BLOCKED")
        self.assertEqual(plan.max_risk_per_trade_idr, 2_500)
        self.assertEqual(plan.daily_max_loss_idr, 10_000)
        self.assertEqual(plan.monthly_max_drawdown_idr, 50_000)

    def test_ready_for_owner_approval_after_readiness(self) -> None:
        plan = build_live_phase_one_plan(
            readiness("READY_FOR_MANUAL_REVIEW"),
            LivePhaseOneConfig(capital_idr=1_000_000),
        )

        self.assertEqual(plan.status, "READY_FOR_OWNER_APPROVAL")
        self.assertIn("owner approval", plan.reason)

    def test_rejects_aggressive_risk(self) -> None:
        with self.assertRaises(ValueError):
            build_live_phase_one_plan(
                readiness("READY_FOR_MANUAL_REVIEW"),
                LivePhaseOneConfig(capital_idr=1_000_000, max_risk_per_trade_pct=1.0),
            )


if __name__ == "__main__":
    unittest.main()
