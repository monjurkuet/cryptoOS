"""Saved Binance account connection and position routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from market_scraper.api.dependencies import get_settings_dependency
from market_scraper.auth.dependencies import (
    CurrentUser,
    get_account_repository,
    require_current_user,
    verify_csrf,
)
from market_scraper.binance_account.client import (
    BinanceAccountClient,
    BinanceAPIError,
    BinanceCredentials,
)
from market_scraper.binance_account.models import (
    BinanceConnectionCreateRequest,
    BinanceConnectionResponse,
    BinanceConnectionsListResponse,
    BinancePositionsResponse,
)
from market_scraper.binance_account.security import CredentialCipher, mask_api_key
from market_scraper.core.config import Settings

router = APIRouter()


def _require_feature_enabled(settings: Settings) -> None:
    if not settings.binance_account.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Binance account positions are disabled",
        )


def _credential_cipher(settings: Settings) -> CredentialCipher:
    try:
        return CredentialCipher.from_settings(settings)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Binance credential encryption is not configured",
        ) from exc


def _connection_response(document: dict[str, Any]) -> BinanceConnectionResponse:
    return BinanceConnectionResponse(
        connection_id=str(document["connection_id"]),
        label=str(document["label"]),
        scope=document["scope"],
        masked_api_key=str(document["masked_api_key"]),
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


@router.post(
    "/connections",
    response_model=BinanceConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    payload: BinanceConnectionCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_current_user),
    repository: Any = Depends(get_account_repository),
    settings: Settings = Depends(get_settings_dependency),
) -> BinanceConnectionResponse:
    """Save encrypted Binance read-only API credentials for the current user."""
    _require_feature_enabled(settings)
    verify_csrf(request, current_user, settings)
    cipher = _credential_cipher(settings)
    now = datetime.now(UTC)
    document = await repository.create_binance_connection(
        {
            "connection_id": str(uuid4()),
            "user_id": current_user.user_id,
            "label": payload.label.strip(),
            "scope": payload.scope.value,
            "api_key_encrypted": cipher.encrypt(payload.api_key.strip()),
            "api_secret_encrypted": cipher.encrypt(payload.api_secret.strip()),
            "masked_api_key": mask_api_key(payload.api_key),
            "created_at": now,
            "updated_at": now,
        }
    )
    return _connection_response(document)


@router.get("/connections", response_model=BinanceConnectionsListResponse)
async def list_connections(
    current_user: CurrentUser = Depends(require_current_user),
    repository: Any = Depends(get_account_repository),
    settings: Settings = Depends(get_settings_dependency),
) -> BinanceConnectionsListResponse:
    """List saved Binance connection metadata for the current user."""
    _require_feature_enabled(settings)
    documents = await repository.list_binance_connections(current_user.user_id)
    return BinanceConnectionsListResponse(
        connections=[_connection_response(document) for document in documents]
    )


@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_current_user),
    repository: Any = Depends(get_account_repository),
    settings: Settings = Depends(get_settings_dependency),
) -> dict[str, bool]:
    """Delete one saved Binance connection."""
    _require_feature_enabled(settings)
    verify_csrf(request, current_user, settings)
    deleted = await repository.delete_binance_connection(current_user.user_id, connection_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return {"ok": True}


@router.get("/positions", response_model=BinancePositionsResponse)
async def get_positions(
    connection_id: str = Query(..., min_length=1),
    include_zero: bool = Query(default=False),
    current_user: CurrentUser = Depends(require_current_user),
    repository: Any = Depends(get_account_repository),
    settings: Settings = Depends(get_settings_dependency),
) -> BinancePositionsResponse:
    """Fetch live Binance spot balances and USD-M futures positions."""
    _require_feature_enabled(settings)
    cipher = _credential_cipher(settings)
    connection = await repository.get_binance_connection(current_user.user_id, connection_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    credentials = BinanceCredentials(
        api_key=cipher.decrypt(str(connection["api_key_encrypted"])),
        api_secret=cipher.decrypt(str(connection["api_secret_encrypted"])),
    )
    try:
        async with BinanceAccountClient(credentials, settings.binance_account) as client:
            return await client.get_positions(
                connection_id=connection_id,
                include_zero=include_zero,
            )
    except BinanceAPIError as exc:
        raise _binance_http_exception(exc) from exc


def _binance_http_exception(exc: BinanceAPIError) -> HTTPException:
    if exc.status_code in {401, 403} or exc.binance_code in {-2014, -2015}:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Binance rejected the API key, secret, or read permissions",
        )
    if exc.status_code in {418, 429}:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Binance rate limit reached; try again later",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Binance account data request failed",
    )
