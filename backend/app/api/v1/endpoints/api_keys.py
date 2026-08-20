###########################################################################################
# This script defines the API key management endpoints for the CRM module.
#
# WHO CAN CREATE KEYS:
#   Only ADMIN users, or MODERATOR users who hold an Agent record, may
#   generate keys. A key is always created for the requesting user's own
#   account — admins cannot generate keys on behalf of other users, since
#   keys are personal CRM credentials, not service accounts.
#
# ROTATION WORKFLOW:
#   1. POST /api-keys                  → generate a new key, note the token
#   2. Update the ApiToken in 3CX      → 3CX now uses the new key
#   3. DELETE /api-keys/{old_id}       → revoke the old key
#   A brief window where both keys are valid (between steps 1 and 3) is
#   intentional — it prevents any call gap during rotation.
###########################################################################################

import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

import hashlib # For hashing the raw secret
from app.core.db import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.enums import UserRole
from app.models.team import Agent
from app.models.api_key import (
    APIKey,
    APIKeyCreate,
    APIKeyUpdate,
    APIKeyCreatedResponse,
    APIKeyResponse,
    APIKeyListResponse,
)

api_keys_router = APIRouter(prefix="/api-keys", tags=["API Keys"])

_KEY_PREFIX = "cx_"


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


async def _caller_is_agent(db: AsyncSession, user_id: int) -> bool:
    """True if the user holds an Agent record — i.e. they are CRM staff."""
    result = (
        await db.exec(select(Agent).where(Agent.user_id == user_id))
    ).one_or_none()
    return result is not None


def _to_response(api_key: APIKey) -> APIKeyResponse:
    return APIKeyResponse(
        id=api_key.id,
        key=api_key.key,
        name=api_key.name,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        date_created=api_key.date_created,
        date_modified=api_key.date_modified,
    )


#############################################
#              GENERATE A KEY               #
#############################################
@api_keys_router.post(
    "",
    response_model=APIKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new CRM API key (Admin or Agent only)",
)
async def create_api_key(
    payload: APIKeyCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> APIKeyCreatedResponse:
    """
    Generates a key/secret pair. The plaintext secret is returned ONCE in
    this response and is never stored or retrievable again — treat the
    `token` field in the response as a password.

    Only admins and users who hold an Agent record may generate keys.
    """
    if not _is_admin(current_user):
        if current_user.role != UserRole.MODERATOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins and moderator agents can generate API keys.",
            )
        if not await _caller_is_agent(db, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be provisioned as an agent before generating a key.",
            )

    # Generate — key is the public half (prefixed), secret is the private half.
    raw_key = _KEY_PREFIX + secrets.token_hex(24)  # "cx_" + 48 hex chars
    raw_secret = secrets.token_hex(32)  # 64 hex chars

    api_key = APIKey(
        key=raw_key,
        hashed_secret=hashlib.sha256(raw_secret.encode('utf-8')).hexdigest(),
        name=payload.name,
        owner_id=current_user.id,
        expires_at=payload.expires_at,
    )
    db.add(api_key)

    try:
        await db.commit()
        await db.refresh(api_key)
    except Exception:
        await db.rollback()
        raise

    return APIKeyCreatedResponse(
        id=api_key.id,
        key=raw_key,
        secret=raw_secret,
        token=f"{raw_key}:{raw_secret}",  # paste this into 3CX's ApiToken field
        name=api_key.name,
        expires_at=api_key.expires_at,
        date_created=api_key.date_created,
    )


#############################################
#               LIST OWN KEYS               #
#############################################
@api_keys_router.get(
    "",
    response_model=APIKeyListResponse,
    summary="List your own API keys (admins can also see all keys)",
)
async def list_api_keys(
    include_inactive: bool = Query(
        False, description="Include revoked/deactivated keys in the results."
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> APIKeyListResponse:
    offset_delta = (page - 1) * limit

    # Admins see every key; others see only their own.
    filters = []
    if not _is_admin(current_user):
        filters.append(APIKey.owner_id == current_user.id)
    if not include_inactive:
        filters.append(APIKey.is_active.is_(True))

    total_count = (await db.exec(select(func.count(APIKey.id)).where(*filters))).one()
    keys = (
        await db.exec(
            select(APIKey)
            .where(*filters)
            .order_by(APIKey.date_created.desc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    return APIKeyListResponse(
        total_count=total_count,
        results=[_to_response(k) for k in keys],
    )


#############################################
#              GET KEY BY ID                #
#############################################
@api_keys_router.get(
    "/{key_id}",
    response_model=APIKeyResponse,
    summary="Get a single API key by ID (owner or admin only)",
)
async def get_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> APIKeyResponse:
    api_key = await db.get(APIKey, key_id)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found."
        )
    if api_key.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found."
        )

    return _to_response(api_key)


#############################################
#           UPDATE KEY (rename / toggle)    #
#############################################
@api_keys_router.patch(
    "/{key_id}",
    response_model=APIKeyResponse,
    summary="Rename a key or toggle its active state (owner or admin only)",
)
async def update_api_key(
    key_id: int,
    payload: APIKeyUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> APIKeyResponse:
    api_key = await db.get(APIKey, key_id)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found."
        )
    if api_key.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found."
        )

    incoming = payload.model_dump(exclude_unset=True)
    if not incoming:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No parameters supplied."
        )

    incoming["date_modified"] = datetime.now(timezone.utc)
    api_key.sqlmodel_update(incoming)
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return _to_response(api_key)


#############################################
#           REVOKE (hard-delete) KEY        #
#############################################
@api_keys_router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently revoke an API key (owner or admin only)",
)
async def delete_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Hard-deletes the key. 3CX will receive 401 on its next call.
    For zero-downtime rotation, generate a new key and update 3CX first
    (PATCH ApiToken in 3CX), then delete the old key here.
    """
    api_key = await db.get(APIKey, key_id)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found."
        )
    if api_key.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found."
        )

    await db.delete(api_key)
    await db.commit()

    return None
