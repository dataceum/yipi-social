"""
APIKey model — CRM-scoped API credentials for the 3CX integration.

Design mirrors how GitHub / Stripe handle personal access tokens:
  - The key (public half) is stored plaintext — safe to index and log.
  - The secret (private half) is bcrypt-hashed before storage, using the
    same get_password_hash / verify_password utilities as User passwords.
    It is returned ONCE at creation and cannot be retrieved again.
  - The combined ApiToken the admin pastes into 3CX is "key:secret".

Only ADMIN and MODERATOR users who already hold an Agent record may own
an API key — enforced at the endpoint layer (api_keys.py). Regular USER
accounts are social-platform members, not CRM staff, so they have no path
to create keys.

A user may hold multiple active keys (e.g. separate keys per 3CX tenant,
or a rotation window where both old and new keys are briefly valid).
Keys can be individually revoked (is_active=False) without touching others.
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
import sqlalchemy as sa

if TYPE_CHECKING:
    from app.models.user import User

#########################################################
#                   API KEY LAYER                        #
#########################################################


class APIKeyCreate(SQLModel):
    """
    The caller supplies only a human-readable label and an optional expiry.
    The key and secret are generated server-side — never client-supplied.
    """

    name: str = Field(
        min_length=3,
        max_length=100,
        description="Human label, e.g. '3CX Main Office' or '3CX Branch 2'.",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Optional UTC expiry. Omit for a non-expiring key.",
    )


class APIKeyUpdate(SQLModel):
    """An owner may rename or deactivate their own key. Reactivating a
    manually-deactivated key (is_active=True) is also permitted — this is
    distinct from an expired key, which cannot be reactivated."""

    name: Optional[str] = None
    is_active: Optional[bool] = None


class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: int = Field(default=None, primary_key=True)

    # Public half — safe to store plaintext, index, and include in logs.
    # Prefixed "cx_" so keys are recognisable at a glance.
    key: str = Field(index=True, unique=True, max_length=64)

    # Private half — bcrypt hash, NEVER returned after creation.
    hashed_secret: str

    name: str = Field(max_length=100)
    owner_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    is_active: bool = Field(default=True)

    last_used_at: Optional[datetime] = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )
    expires_at: Optional[datetime] = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )
    date_created: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    date_modified: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    owner: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[APIKey.owner_id]",
            "lazy": "selectin",
        },
    )


##########################################################
# OUTGOING RESPONSE PAYLOAD DATA TRANSFER OBJECTS (DTOs) #
##########################################################


class APIKeyCreatedResponse(SQLModel):
    """
    Returned ONCE at creation — the only time the plaintext secret is
    visible. The `token` field is the ready-to-paste 3CX ApiToken value.
    Store it somewhere safe; there is no way to retrieve the secret again.
    """

    id: int
    key: str
    secret: str  # plaintext, shown once only
    token: str  # convenience: "key:secret" — paste into 3CX
    name: str
    expires_at: Optional[datetime] = None
    date_created: datetime


class APIKeyResponse(SQLModel):
    """Normal response for list/get/update operations — secret is never
    included. The key is shown so the owner can identify which record is
    which without exposing the secret."""

    id: int
    key: str  # safe to display — it's the public half
    name: str
    is_active: bool
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    date_created: datetime
    date_modified: datetime


class APIKeyListResponse(SQLModel):
    total_count: int
    results: List[APIKeyResponse]
