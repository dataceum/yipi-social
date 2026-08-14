###############################################
# Token Layer for Security and Authentication #
###############################################


import sqlalchemy as sa
from datetime import datetime, timedelta, timezone
from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from app.models.user import User


class TokenBase(SQLModel):
    """
    Core attributes for token tracking and lifecycle
    """

    refresh_token: str = Field(index=True, unique=True)
    user_agent: Optional[str] = Field(
        default=None, max_length=255, description="Tracks device browser/device metrics"
    )
    client_ip: Optional[str] = Field(
        default=None,
        max_length=45,
        description="Client's IPv4 or IPv6 tracking address",
    )


class TokenCreate(TokenBase):
    """
    Schema used inside login endpiont to provision a state tracking session during a login request.
    """

    user_id: int


class RefreshRequest(SQLModel):
    """
    The JSON payload sent by the frontend when its access token expires.
    """

    refresh_token: str


class Token(TokenBase, table=True):
    """
    Physical database session table stored in the database
    """

    __tablename__ = "user_tokens"

    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    is_revoked: bool = Field(
        default=False, index=True, description="Allows instant token revocation"
    )

    # Audit footpring
    date_created: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    date_modified: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    modified_by: Optional[int] = Field(
        default=None, foreign_key="users.id", nullable=True
    )

    # Enforces a strict 30-day session lease limit on disk storage
    expires_at: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30),
        index=True,
    )

    # Relationship linking back to the parent User model
    user: "User" = Relationship(
        back_populates="tokens",
        sa_relationship_kwargs={
            "foreign_keys": "[Token.user_id]",
            "lazy": "selectin",
        },
    )


class TokenSetResponse(SQLModel):
    """
    The JSON payload returned to the frontend library for successful login/refresh actions.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(SQLModel):
    """Internal validation schema matching decrypted JWT Access Token payload data structures."""

    user_id: int
    username: str
