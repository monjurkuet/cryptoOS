"""Tests for saved Binance account routes."""

# ruff: noqa: D102,D105

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from market_scraper.api.dependencies import get_lifecycle, get_settings_dependency
from market_scraper.api.routes import binance_account as routes
from market_scraper.auth.security import hash_token
from market_scraper.binance_account.models import (
    BinanceAccountScope,
    BinancePositionsResponse,
    BinanceTotalsResponse,
)
from market_scraper.core.config import Settings


class FakeAccountRepository:
    """Minimal account repository for Binance route tests."""

    def __init__(self) -> None:
        self.user = {"user_id": "user_1", "email": "user@example.com"}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.connections: dict[str, dict[str, Any]] = {}

    async def get_app_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self.user if user_id == self.user["user_id"] else None

    async def get_auth_session_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        return self.sessions.get(token_hash)

    async def delete_auth_session(self, token_hash: str) -> bool:
        return self.sessions.pop(token_hash, None) is not None

    async def update_auth_session_csrf(self, token_hash: str, csrf_hash: str) -> bool:
        self.sessions[token_hash]["csrf_hash"] = csrf_hash
        return True

    async def create_binance_connection(self, connection: dict[str, Any]) -> dict[str, Any]:
        document = dict(connection)
        self.connections[document["connection_id"]] = document
        return dict(document)

    async def list_binance_connections(self, user_id: str) -> list[dict[str, Any]]:
        return [
            dict(connection)
            for connection in self.connections.values()
            if connection["user_id"] == user_id
        ]

    async def get_binance_connection(
        self, user_id: str, connection_id: str
    ) -> dict[str, Any] | None:
        connection = self.connections.get(connection_id)
        if not connection or connection["user_id"] != user_id:
            return None
        return dict(connection)

    async def delete_binance_connection(self, user_id: str, connection_id: str) -> bool:
        connection = self.connections.get(connection_id)
        if not connection or connection["user_id"] != user_id:
            return False
        del self.connections[connection_id]
        return True


class FakeBinanceAccountClient:
    """Fake Binance client that validates decrypted credentials."""

    def __init__(self, credentials: Any, _settings: Any) -> None:
        self.credentials = credentials

    async def __aenter__(self) -> FakeBinanceAccountClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def get_positions(
        self,
        connection_id: str,
        include_zero: bool = False,
    ) -> BinancePositionsResponse:
        assert self.credentials.api_key == "plain-api-key"
        assert self.credentials.api_secret == "plain-api-secret"
        assert include_zero is True
        return BinancePositionsResponse(
            connection_id=connection_id,
            as_of=datetime.now(UTC),
            account_scope=BinanceAccountScope.SPOT_AND_USDM_FUTURES,
            totals=BinanceTotalsResponse(
                estimated_usdt_value=1.0,
                spot_value_usdt=1.0,
                futures_wallet_balance_usdt=0.0,
                futures_unrealized_pnl_usdt=0.0,
            ),
            spot_balances=[],
            futures_positions=[],
            warnings=[],
        )


@pytest.fixture
def app_context() -> tuple[FastAPI, FakeAccountRepository, Settings, str, str]:
    """Create a test app with an authenticated session."""
    repository = FakeAccountRepository()
    lifecycle = type("Lifecycle", (), {"repository": repository})()
    settings = Settings(
        _env_file=None,
        mongo={"url": "mongodb://localhost:27017"},
        binance_account={"encryption_key": Fernet.generate_key().decode("utf-8")},
    )
    session_token = "session-token"
    csrf_token = "csrf-token"
    repository.sessions[hash_token(session_token)] = {
        "session_id": "session_1",
        "user_id": "user_1",
        "token_hash": hash_token(session_token),
        "csrf_hash": hash_token(csrf_token),
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }

    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1/binance")
    app.dependency_overrides[get_lifecycle] = lambda: lifecycle
    app.dependency_overrides[get_settings_dependency] = lambda: settings
    return app, repository, settings, session_token, csrf_token


@pytest.mark.asyncio
async def test_connection_lifecycle_and_positions(
    app_context: tuple[FastAPI, FakeAccountRepository, Settings, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Save encrypted credentials, view positions, and delete the connection."""
    app, repository, settings, session_token, csrf_token = app_context
    monkeypatch.setattr(routes, "BinanceAccountClient", FakeBinanceAccountClient)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set(settings.auth.session_cookie_name, session_token)
        missing_csrf = await client.post(
            "/api/v1/binance/connections",
            json={
                "label": "Primary <script>",
                "api_key": "plain-api-key",
                "api_secret": "plain-api-secret",
            },
        )
        assert missing_csrf.status_code == 403

        created = await client.post(
            "/api/v1/binance/connections",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "label": "Primary <script>",
                "api_key": "plain-api-key",
                "api_secret": "plain-api-secret",
            },
        )
        assert created.status_code == 201
        created_body = created.json()
        assert created_body["label"] == "Primary <script>"
        assert created_body["masked_api_key"] == "plai...-key"
        assert "api_key" not in created_body
        connection_id = created_body["connection_id"]

        stored = repository.connections[connection_id]
        assert stored["api_key_encrypted"] != "plain-api-key"
        assert stored["api_secret_encrypted"] != "plain-api-secret"

        listed = await client.get("/api/v1/binance/connections")
        assert listed.status_code == 200
        assert listed.json()["connections"][0]["connection_id"] == connection_id

        positions = await client.get(
            f"/api/v1/binance/positions?connection_id={connection_id}&include_zero=true"
        )
        assert positions.status_code == 200
        assert positions.json()["totals"]["estimated_usdt_value"] == 1.0

        deleted = await client.delete(
            f"/api/v1/binance/connections/{connection_id}",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert deleted.status_code == 200
        assert connection_id not in repository.connections
