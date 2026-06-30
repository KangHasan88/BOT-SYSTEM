from __future__ import annotations

import json
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from trading_bot.data_collector.market_context import (
    OrderBookSnapshot,
    SymbolMetadata,
    TickerSnapshot,
)
from trading_bot.data_collector.models import Candle


class BinancePublicKlineClient:
    def __init__(self, base_url: str = "https://api.binance.com") -> None:
        self.base_url = base_url.rstrip("/")

    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
        start_time_ms: int | None = None,
    ) -> list[Candle]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")

        params: dict[str, str | int] = {
            "symbol": symbol.replace("/", ""),
            "interval": timeframe,
            "limit": limit,
        }
        if start_time_ms is not None:
            params["startTime"] = start_time_ms

        url = f"{self.base_url}/api/v3/klines?{urlencode(params)}"
        with urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        return [self._parse_kline(symbol, timeframe, row) for row in payload]

    def _parse_kline(self, symbol: str, timeframe: str, row: list[object]) -> Candle:
        return Candle(
            symbol=symbol,
            timeframe=timeframe,
            open_time_ms=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            close_time_ms=int(row[6]),
            source="binance_public",
        )

    def fetch_ticker_snapshot(self, symbol: str) -> TickerSnapshot:
        params = {"symbol": symbol.replace("/", "")}
        url = f"{self.base_url}/api/v3/ticker/bookTicker?{urlencode(params)}"
        with urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        return TickerSnapshot(
            symbol=symbol,
            captured_at_ms=int(time.time() * 1000),
            bid=float(payload["bidPrice"]),
            ask=float(payload["askPrice"]),
            source="binance_public",
        )

    def fetch_order_book_snapshot(self, symbol: str, limit: int = 20) -> OrderBookSnapshot:
        params = {"symbol": symbol.replace("/", ""), "limit": limit}
        url = f"{self.base_url}/api/v3/depth?{urlencode(params)}"
        with urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        bids = [(float(price), float(quantity)) for price, quantity in payload["bids"]]
        asks = [(float(price), float(quantity)) for price, quantity in payload["asks"]]
        bid_notional = sum(price * quantity for price, quantity in bids)
        ask_notional = sum(price * quantity for price, quantity in asks)

        return OrderBookSnapshot(
            symbol=symbol,
            captured_at_ms=int(time.time() * 1000),
            best_bid=bids[0][0] if bids else 0.0,
            best_ask=asks[0][0] if asks else 0.0,
            bid_notional_top=bid_notional,
            ask_notional_top=ask_notional,
            source="binance_public",
        )

    def fetch_symbol_metadata(
        self,
        symbol: str,
        taker_fee_pct: float = 0.10,
        maker_fee_pct: float = 0.10,
    ) -> SymbolMetadata:
        params = {"symbol": symbol.replace("/", "")}
        url = f"{self.base_url}/api/v3/exchangeInfo?{urlencode(params)}"
        with urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        raw_symbol = payload["symbols"][0]
        min_notional = 0.0
        for item in raw_symbol.get("filters", []):
            if item.get("filterType") in {"MIN_NOTIONAL", "NOTIONAL"}:
                min_notional = float(item.get("minNotional", 0.0))
                break

        return SymbolMetadata(
            symbol=symbol,
            base_asset=raw_symbol["baseAsset"],
            quote_asset=raw_symbol["quoteAsset"],
            min_notional=min_notional,
            price_precision=int(raw_symbol.get("quotePrecision", 0)),
            quantity_precision=int(raw_symbol.get("baseAssetPrecision", 0)),
            taker_fee_pct=taker_fee_pct,
            maker_fee_pct=maker_fee_pct,
            source="binance_public",
        )
