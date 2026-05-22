"""Tests for local auth routes."""

# ruff: noqa: D102

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from market_scraper.api.dependencies import get_settings_dependency
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
    app.dependency_overrides[get_settings_dependency] = lambda: app.state.settings
    return app


def _extract_session_cookie(response: Any) -> str:
    """Extract the cryptoos_session cookie value from a Set-Cookie header."""
    set_cookie = response.headers.get("set-cookie", "")
    for part in set_cookie.split(";"):
        part = part.strip()
        if part.startswith("cryptoos_session="):
            return part.split("=", 1)[1]
    return ""


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

        # httpx ASGITransport does not auto-forward Set-Cookie to subsequent
        # requests, so we must set the session cookie on the client manually.
        session_cookie = _extract_session_cookie(register)
        assert session_cookie, "Session cookie not set in register response"
        client.cookies.set("cryptoos_session", session_cookie)

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

        # After logout the session is deleted server-side; re-set the stale
        # cookie so the request carries it and we verify 401.
        client.cookies.set("cryptoos_session", session_cookie)
        after_logout = await client.get("/api/v1/auth/me")
        assert after_logout.status_code == 401


@pytest.mark.asyncio
async def test_me_accepts_naive_expiry_datetime(app: FastAPI) -> None:
    """Sessions with naive expiry datetimes are treated as UTC."""
    lifecycle = app.dependency_overrides[get_lifecycle]()  # type: ignore[call-arg]
    repository = lifecycle.repository

    user_id = "user-naive"
    session_token = "naive-session-token"
    repository.users_by_id[user_id] = {
        "user_id": user_id,
        "email": "naive@example.com",
        "password_hash": "unused",
    }
    repository.users_by_email["naive@example.com"] = repository.users_by_id[user_id]
    repository.sessions[hash_token(session_token)] = {
        "session_id": "session-naive",
        "user_id": user_id,
        "token_hash": hash_token(session_token),
        "csrf_hash": hash_token("csrf-old"),
        # Deliberately timezone-naive, as can happen with legacy BSON codecs.
        "expires_at": datetime.utcnow() + timedelta(hours=1),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("cryptoos_session", session_token)
        me = await client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["email"] == "naive@example.com"
