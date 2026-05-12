"""Read-only Binance account client."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode

import httpx

from market_scraper.binance_account.models import (
    BinanceAccountScope,
    BinancePositionsResponse,
    BinanceTotalsResponse,
    FuturesPositionResponse,
    SpotBalanceResponse,
)
from market_scraper.core.config import BinanceAccountSettings


class BinanceAPIError(RuntimeError):
    """Raised when Binance rejects or fails a request."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        binance_code: int | None = None,
    ) -> None:
        """Initialize a Binance API error."""
        super().__init__(message)
        self.status_code = status_code
        self.binance_code = binance_code


@dataclass(frozen=True)
class BinanceCredentials:
    """Read-only Binance API credentials."""

    api_key: str
    api_secret: str


class BinanceAccountClient:
    """Fetch Binance spot balances and USD-M futures positions."""

    def __init__(
        self,
        credentials: BinanceCredentials,
        settings: BinanceAccountSettings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the Binance client."""
        self._credentials = credentials
        self._settings = settings
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.timeout_seconds),
            headers={"Accept": "application/json", "User-Agent": "cryptoOS/market-scraper"},
        )
        self._owns_client = http_client is None
        self._time_offsets_ms: dict[str, int] = {}
        self.warnings: list[str] = []

    async def __aenter__(self) -> BinanceAccountClient:
        """Enter async context."""
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Close the owned HTTP client."""
        await self.close()

    async def close(self) -> None:
        """Close the owned HTTP client."""
        if self._owns_client:
            await self._client.aclose()

    async def get_positions(
        self,
        connection_id: str,
        include_zero: bool = False,
    ) -> BinancePositionsResponse:
        """Fetch combined spot balances and USD-M futures positions."""
        spot_account = await self.get_spot_account()
        prices = await self.get_spot_prices()
        futures_account = await self.get_usdm_account()
        futures_positions_raw = await self.get_usdm_positions()

        spot_balances = self._normalize_spot_balances(
            spot_account.get("balances", []),
            prices,
            include_zero=include_zero,
        )
        futures_positions = self._normalize_futures_positions(
            futures_positions_raw,
            include_zero=include_zero,
        )

        spot_value = sum(
            Decimal(str(balance.value_usdt))
            for balance in spot_balances
            if balance.value_usdt is not None
        )
        futures_wallet = _decimal(futures_account.get("totalWalletBalance"))
        futures_upnl = _decimal(futures_account.get("totalUnrealizedProfit"))
        totals = BinanceTotalsResponse(
            estimated_usdt_value=float(spot_value + futures_wallet + futures_upnl),
            spot_value_usdt=float(spot_value),
            futures_wallet_balance_usdt=float(futures_wallet),
            futures_unrealized_pnl_usdt=float(futures_upnl),
        )

        return BinancePositionsResponse(
            connection_id=connection_id,
            as_of=datetime.now(UTC),
            account_scope=BinanceAccountScope.SPOT_AND_USDM_FUTURES,
            totals=totals,
            spot_balances=spot_balances,
            futures_positions=futures_positions,
            warnings=list(dict.fromkeys(self.warnings)),
        )

    async def get_spot_account(self) -> dict[str, Any]:
        """Fetch Binance Spot account balances."""
        data = await self._signed_request("spot", "GET", "/api/v3/account")
        return data if isinstance(data, dict) else {}

    async def get_spot_prices(self) -> dict[str, Decimal]:
        """Fetch Binance Spot symbol prices."""
        data = await self._public_request("spot", "GET", "/api/v3/ticker/price")
        prices: dict[str, Decimal] = {}
        if isinstance(data, list):
            for row in data:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("symbol", "")).upper()
                price = _decimal(row.get("price"))
                if symbol and price > 0:
                    prices[symbol] = price
        return prices

    async def get_usdm_account(self) -> dict[str, Any]:
        """Fetch Binance USD-M futures account information."""
        data = await self._signed_request("futures", "GET", "/fapi/v3/account")
        return data if isinstance(data, dict) else {}

    async def get_usdm_positions(self) -> list[dict[str, Any]]:
        """Fetch Binance USD-M futures position risk rows."""
        data = await self._signed_request("futures", "GET", "/fapi/v3/positionRisk")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        return []

    async def _public_request(self, market: str, method: str, path: str) -> Any:
        base_url = self._base_url(market)
        response = await self._client.request(method, f"{base_url}{path}")
        return self._handle_response(response)

    async def _signed_request(
        self,
        market: str,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        retry_on_timestamp_error: bool = True,
    ) -> Any:
        if market not in self._time_offsets_ms:
            await self._sync_time(market)

        signed_params = dict(params or {})
        signed_params["timestamp"] = int(time.time() * 1000) + self._time_offsets_ms[market]
        signed_params["recvWindow"] = self._settings.recv_window_ms
        query_string = urlencode(signed_params, doseq=True)
        signed_params["signature"] = hmac.new(
            self._credentials.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        response = await self._client.request(
            method,
            f"{self._base_url(market)}{path}",
            params=signed_params,
            headers={"X-MBX-APIKEY": self._credentials.api_key},
        )

        try:
            return self._handle_response(response)
        except BinanceAPIError as exc:
            if retry_on_timestamp_error and exc.binance_code == -1021:
                await self._sync_time(market)
                self.warnings.append("Binance timestamp drift detected; request retried")
                return await self._signed_request(
                    market,
                    method,
                    path,
                    params=params,
                    retry_on_timestamp_error=False,
                )
            raise

    async def _sync_time(self, market: str) -> None:
        time_path = "/api/v3/time" if market == "spot" else "/fapi/v1/time"
        data = await self._public_request(market, "GET", time_path)
        if not isinstance(data, dict) or "serverTime" not in data:
            self._time_offsets_ms[market] = 0
            self.warnings.append(f"Unable to sync Binance {market} server time")
            return
        server_time_ms = int(data["serverTime"])
        local_time_ms = int(time.time() * 1000)
        self._time_offsets_ms[market] = server_time_ms - local_time_ms

    def _handle_response(self, response: httpx.Response) -> Any:
        try:
            data = response.json()
        except ValueError:
            data = {"msg": response.text}

        if response.status_code < 400:
            return data

        message = "Binance request failed"
        code = None
        if isinstance(data, dict):
            message = str(data.get("msg") or message)
            raw_code = data.get("code")
            if isinstance(raw_code, int):
                code = raw_code
            elif isinstance(raw_code, str) and raw_code.lstrip("-").isdigit():
                code = int(raw_code)

        raise BinanceAPIError(message, status_code=response.status_code, binance_code=code)

    def _base_url(self, market: str) -> str:
        if market == "spot":
            return self._settings.spot_base_url.rstrip("/")
        return self._settings.futures_base_url.rstrip("/")

    def _normalize_spot_balances(
        self,
        balances: Any,
        prices: dict[str, Decimal],
        *,
        include_zero: bool,
    ) -> list[SpotBalanceResponse]:
        normalized: list[SpotBalanceResponse] = []
        if not isinstance(balances, list):
            return normalized

        for row in balances:
            if not isinstance(row, dict):
                continue
            asset = str(row.get("asset", "")).upper()
            free = _decimal(row.get("free"))
            locked = _decimal(row.get("locked"))
            total = free + locked
            if not include_zero and total == 0:
                continue

            price_usdt: Decimal | None
            value_usdt: Decimal | None
            if asset in {"USDT", "FDUSD", "USDC"}:
                price_usdt = Decimal("1")
                value_usdt = total
            else:
                price_usdt = prices.get(f"{asset}USDT")
                value_usdt = total * price_usdt if price_usdt is not None else None
                if total > 0 and price_usdt is None:
                    self.warnings.append(f"No USDT spot price found for {asset}")

            normalized.append(
                SpotBalanceResponse(
                    asset=asset,
                    free=float(free),
                    locked=float(locked),
                    total=float(total),
                    price_usdt=float(price_usdt) if price_usdt is not None else None,
                    value_usdt=float(value_usdt) if value_usdt is not None else None,
                )
            )

        normalized.sort(key=lambda item: item.value_usdt or 0.0, reverse=True)
        return normalized

    @staticmethod
    def _normalize_futures_positions(
        positions: list[dict[str, Any]],
        *,
        include_zero: bool,
    ) -> list[FuturesPositionResponse]:
        normalized: list[FuturesPositionResponse] = []
        for row in positions:
            position_amt = _decimal(row.get("positionAmt"))
            if not include_zero and position_amt == 0:
                continue
            mark_price = _decimal(row.get("markPrice"))
            notional = _decimal(row.get("notional"))
            if notional == 0 and mark_price > 0:
                notional = position_amt * mark_price
            liquidation = _decimal(row.get("liquidationPrice"))
            normalized.append(
                FuturesPositionResponse(
                    symbol=str(row.get("symbol", "")).upper(),
                    side=_position_side(position_amt, row.get("positionSide")),
                    position_amt=float(position_amt),
                    entry_price=float(_decimal(row.get("entryPrice"))),
                    mark_price=float(mark_price),
                    notional_usdt=float(notional),
                    unrealized_pnl=float(_decimal(row.get("unRealizedProfit"))),
                    leverage=float(_decimal(row.get("leverage"), default=Decimal("1"))),
                    margin_type=str(row.get("marginType", "")),
                    liquidation_price=float(liquidation) if liquidation > 0 else None,
                )
            )
        normalized.sort(key=lambda item: abs(item.notional_usdt), reverse=True)
        return normalized


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _position_side(position_amt: Decimal, position_side: Any = None) -> str:
    normalized_side = str(position_side or "").lower()
    if normalized_side in {"long", "short"}:
        return normalized_side
    if position_amt > 0:
        return "long"
    if position_amt < 0:
        return "short"
    return "flat"
