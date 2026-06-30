import unittest

from trading_bot.execution import ExchangeOrderRequest, ExecutionSafetyError, SandboxExchangeAdapter


class SandboxExecutionTest(unittest.TestCase):
    def test_market_order_is_filled_in_sandbox(self) -> None:
        adapter = SandboxExchangeAdapter()
        order = adapter.place_order(
            ExchangeOrderRequest(
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                quantity=0.01,
            )
        )

        self.assertEqual(order.status, "FILLED")
        self.assertEqual(order.source, "sandbox")
        self.assertEqual(adapter.query_order(order.order_id), order)

    def test_limit_order_can_be_canceled(self) -> None:
        adapter = SandboxExchangeAdapter("testnet")
        order = adapter.place_order(
            ExchangeOrderRequest(
                symbol="ETH/USDT",
                side="buy",
                order_type="limit",
                quantity=0.5,
                price=2_500.0,
            )
        )
        canceled = adapter.cancel_order(order.order_id)

        self.assertEqual(order.status, "OPEN")
        self.assertEqual(canceled.status, "CANCELED")
        self.assertEqual(canceled.source, "testnet")

    def test_live_environment_is_rejected(self) -> None:
        with self.assertRaises(ExecutionSafetyError):
            SandboxExchangeAdapter("live")

    def test_unknown_symbol_is_rejected(self) -> None:
        adapter = SandboxExchangeAdapter()
        with self.assertRaises(ExecutionSafetyError):
            adapter.place_order(
                ExchangeOrderRequest(
                    symbol="DOGE/USDT",
                    side="buy",
                    order_type="market",
                    quantity=1.0,
                )
            )


if __name__ == "__main__":
    unittest.main()
