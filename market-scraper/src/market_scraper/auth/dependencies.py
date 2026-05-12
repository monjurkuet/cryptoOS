"""FastAPI dependencies for local account authentication."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from market_scraper.api.dependencies import get_lifecycle, get_settings_dependency
from market_scraper.auth.security import hash_token
from market_scraper.core.config import Settings
from market_scraper.orchestration.lifecycle import LifecycleManager


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated local user and session context."""

    user_id: str
    email: str
    session_id: str
    token_hash: str
    csrf_hash: str


def get_account_repository(lifecycle: LifecycleManager = Depends(get_lifecycle)) -> Any:
    """Return a repository that supports account storage."""
    repository = lifecycle.repository
    required_methods = (
        "get_app_user_by_id",
        "get_auth_session_by_token_hash",
        "update_auth_session_csrf",
        "create_binance_connection",
    )
    if repository is None or not all(hasattr(repository, method) for method in required_methods):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB account storage is required for this feature",
        )
    return repository


async def require_current_user(
    request: Request,
    repository: Any = Depends(get_account_repository),
    settings: Settings = Depends(get_settings_dependency),
) -> CurrentUser:
    """Require a valid session cookie and return the current user context."""
    session_token = request.cookies.get(settings.auth.session_cookie_name)
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token_hash = hash_token(session_token)
    session = await repository.get_auth_session_by_token_hash(token_hash)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    expires_at = session.get("expires_at")
    if not isinstance(expires_at, datetime) or expires_at <= datetime.now(UTC):
        await repository.delete_auth_session(token_hash)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user = await repository.get_app_user_by_id(str(session.get("user_id", "")))
    if not user:
        await repository.delete_auth_session(token_hash)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return CurrentUser(
        user_id=str(user["user_id"]),
        email=str(user["email"]),
        session_id=str(session["session_id"]),
        token_hash=token_hash,
        csrf_hash=str(session["csrf_hash"]),
    )


def verify_csrf(
    request: Request,
    current_user: CurrentUser,
    settings: Settings,
) -> None:
    """Validate the CSRF header for state-changing authenticated requests."""
    csrf_token = request.headers.get(settings.auth.csrf_header_name)
    if not csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing CSRF token")
    if not secrets.compare_digest(hash_token(csrf_token), current_user.csrf_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
