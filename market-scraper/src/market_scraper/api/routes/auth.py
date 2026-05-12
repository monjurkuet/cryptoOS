"""Local account authentication routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from market_scraper.api.dependencies import get_settings_dependency
from market_scraper.auth.dependencies import (
    CurrentUser,
    get_account_repository,
    require_current_user,
    verify_csrf,
)
from market_scraper.auth.security import (
    hash_password,
    hash_token,
    new_secret_token,
    normalize_email,
    session_expires_at,
    verify_password,
)
from market_scraper.core.config import Settings

router = APIRouter()


class AuthCredentialsRequest(BaseModel):
    """Email/password auth request."""

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)


class AuthUserResponse(BaseModel):
    """Authenticated user response."""

    user_id: str
    email: str


class AuthSessionResponse(BaseModel):
    """Auth response containing the CSRF token needed for writes."""

    user: AuthUserResponse
    csrf_token: str


def _public_user(user: dict[str, Any]) -> AuthUserResponse:
    return AuthUserResponse(user_id=str(user["user_id"]), email=str(user["email"]))


def _set_session_cookie(
    response: Response,
    settings: Settings,
    session_token: str,
    expires_at: datetime,
) -> None:
    max_age = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        settings.auth.session_cookie_name,
        session_token,
        max_age=max_age,
        expires=expires_at,
        httponly=True,
        secure=settings.auth.session_cookie_secure,
        samesite="lax",
        path="/",
    )


async def _create_session(
    repository: Any,
    user_id: str,
    settings: Settings,
) -> tuple[str, str, datetime]:
    session_token = new_secret_token()
    csrf_token = new_secret_token()
    expires_at = session_expires_at(settings.auth.session_ttl_hours)
    await repository.create_auth_session(
        {
            "session_id": str(uuid4()),
            "user_id": user_id,
            "token_hash": hash_token(session_token),
            "csrf_hash": hash_token(csrf_token),
            "created_at": datetime.now(UTC),
            "expires_at": expires_at,
        }
    )
    return session_token, csrf_token, expires_at


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: AuthCredentialsRequest,
    response: Response,
    repository: Any = Depends(get_account_repository),
    settings: Settings = Depends(get_settings_dependency),
) -> AuthSessionResponse:
    """Create a local user account and start a session."""
    try:
        email = normalize_email(request.email)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if len(request.password) < settings.auth.password_min_length:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must be at least {settings.auth.password_min_length} characters",
        )

    existing = await repository.get_app_user_by_email(email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    now = datetime.now(UTC)
    user = await repository.create_app_user(
        {
            "user_id": str(uuid4()),
            "email": email,
            "password_hash": hash_password(request.password),
            "created_at": now,
            "updated_at": now,
        }
    )
    session_token, csrf_token, expires_at = await _create_session(
        repository, str(user["user_id"]), settings
    )
    _set_session_cookie(response, settings, session_token, expires_at)
    return AuthSessionResponse(user=_public_user(user), csrf_token=csrf_token)


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    request: AuthCredentialsRequest,
    response: Response,
    repository: Any = Depends(get_account_repository),
    settings: Settings = Depends(get_settings_dependency),
) -> AuthSessionResponse:
    """Start a session for an existing local user."""
    try:
        email = normalize_email(request.email)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    user = await repository.get_app_user_by_email(email)
    if not user or not verify_password(request.password, str(user.get("password_hash", ""))):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    session_token, csrf_token, expires_at = await _create_session(
        repository, str(user["user_id"]), settings
    )
    _set_session_cookie(response, settings, session_token, expires_at)
    return AuthSessionResponse(user=_public_user(user), csrf_token=csrf_token)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: CurrentUser = Depends(require_current_user),
    repository: Any = Depends(get_account_repository),
    settings: Settings = Depends(get_settings_dependency),
) -> dict[str, bool]:
    """End the current local session."""
    verify_csrf(request, current_user, settings)
    await repository.delete_auth_session(current_user.token_hash)
    response.delete_cookie(settings.auth.session_cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=AuthSessionResponse)
async def me(
    current_user: CurrentUser = Depends(require_current_user),
    repository: Any = Depends(get_account_repository),
) -> AuthSessionResponse:
    """Return the authenticated user and rotate a CSRF token for writes."""
    csrf_token = new_secret_token()
    await repository.update_auth_session_csrf(current_user.token_hash, hash_token(csrf_token))
    return AuthSessionResponse(
        user=AuthUserResponse(user_id=current_user.user_id, email=current_user.email),
        csrf_token=csrf_token,
    )
