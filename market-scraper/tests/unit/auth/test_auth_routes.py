"""Tests for local auth routes."""

# ruff: noqa: D102

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from market_scraper.api.dependencies import get_lifecycle
from market_scraper.api.routes.auth import router
from market_scraper.auth.security import hash_token
from market_scraper.core.config import Settings


class FakeAccountRepository:
    """Minimal in-memory account repository for route tests."""

    def __init__(self) -> None:
        self.users_by_email: dict[str, dict[str, Any]] = {}
        self.users_by_id: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}

    async def create_app_user(self, user: dict[str, Any]) -> dict[str, Any]:
        self.users_by_email[user["email"]] = dict(user)
        self.users_by_id[user["user_id"]] = dict(user)
        return dict(user)

    async def get_app_user_by_email(self, email: str) -> dict[str, Any] | None:
        return self.users_by_email.get(email)

    async def get_app_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self.users_by_id.get(user_id)

    async def create_auth_session(self, session: dict[str, Any]) -> dict[str, Any]:
        self.sessions[session["token_hash"]] = dict(session)
        return dict(session)

    async def get_auth_session_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        return self.sessions.get(token_hash)

    async def delete_auth_session(self, token_hash: str) -> bool:
        return self.sessions.pop(token_hash, None) is not None

    async def update_auth_session_csrf(self, token_hash: str, csrf_hash: str) -> bool:
        self.sessions[token_hash]["csrf_hash"] = csrf_hash
        self.sessions[token_hash]["updated_at"] = datetime.now(UTC)
        return True

    async def create_binance_connection(self, connection: dict[str, Any]) -> dict[str, Any]:
        return dict(connection)


@pytest.fixture
def app() -> FastAPI:
    """Create a test app with fake account storage."""
    repository = FakeAccountRepository()
    lifecycle = type("Lifecycle", (), {"repository": repository})()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/auth")
    app.dependency_overrides[get_lifecycle] = lambda: lifecycle
    app.state.settings = Settings(
        mongo={"url": "mongodb://localhost:27017"},
        binance_account={"encryption_key": Fernet.generate_key().decode("utf-8")},
    )
    return app


@pytest.mark.asyncio
async def test_register_me_logout_flow(app: FastAPI) -> None:
    """Register, rotate CSRF through /me, and logout."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        register = await client.post(
            "/api/v1/auth/register",
            json={"email": "User@Example.com", "password": "strong-passphrase"},
        )
        assert register.status_code == 201
        csrf_token = register.json()["csrf_token"]
        assert csrf_token
        assert register.json()["user"]["email"] == "user@example.com"

        me = await client.get("/api/v1/auth/me")
        assert me.status_code == 200
        rotated_csrf = me.json()["csrf_token"]
        assert rotated_csrf
        assert hash_token(rotated_csrf) != hash_token(csrf_token)

        logout = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": rotated_csrf},
            json={},
        )
        assert logout.status_code == 200

        after_logout = await client.get("/api/v1/auth/me")
        assert after_logout.status_code == 401
