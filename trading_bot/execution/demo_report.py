from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from trading_bot.execution.models import ExchangeOrder, ExchangeOrderRequest, ExecutionSafetyError
from trading_bot.execution.sandbox import SandboxExchangeAdapter


@dataclass(frozen=True)
class TestnetDemoReport:
    status: str
    environment: str
    generated_at_utc: str
    orders: list[ExchangeOrder]
    live_guard_status: str
    live_guard_reason: str
    notes: list[str]


def run_testnet_demo_report(environment: str = "testnet") -> TestnetDemoReport:
    adapter = SandboxExchangeAdapter(environment)
    orders: list[ExchangeOrder] = []
    orders.append(
        adapter.place_order(
            ExchangeOrderRequest(
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                quantity=0.001,
                client_order_id="demo-market-buy",
            )
        )
    )
    limit_order = adapter.place_order(
        ExchangeOrderRequest(
            symbol="ETH/USDT",
            side="sell",
            order_type="limit",
            quantity=0.01,
            price=3_500.0,
            client_order_id="demo-limit-sell",
        )
    )
    orders.append(limit_order)
    orders.append(adapter.cancel_order(limit_order.order_id))

    live_guard_status = "PASS"
    live_guard_reason = "live environment rejected"
    try:
        SandboxExchangeAdapter("live")
    except ExecutionSafetyError as exc:
        live_guard_reason = str(exc)
    else:
        live_guard_status = "FAIL"
        live_guard_reason = "live environment was not rejected"

    status = "PASSED" if live_guard_status == "PASS" and all(order.source == environment for order in orders) else "FAILED"
    return TestnetDemoReport(
        status=status,
        environment=environment,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        orders=orders,
        live_guard_status=live_guard_status,
        live_guard_reason=live_guard_reason,
        notes=[
            "demo account flow uses sandbox/testnet adapter only",
            "no real exchange key or withdrawal permission is required",
            "real live routing remains blocked",
        ],
    )


def save_testnet_demo_report(report: TestnetDemoReport, root: str | Path) -> Path:
    path = Path(root) / "execution" / "testnet_demo" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return path
