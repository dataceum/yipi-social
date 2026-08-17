"""This script defines the User Profile models and schemas for the application using SQLModel, which is a library that combines Pydantic and SQLAlchemy to provide a simple way to define database models with validation by emulating SQLAlchemy's ORM behavior."""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
import sqlalchemy as sa
from app.models.enums import (
    AgeCategory,
    ProfileStatus,
    RejectionReason,
)

if TYPE_CHECKING:
    from app.models.user import User

#########################################################
#                   USER PROFILE LAYER                  #
#########################################################


class ProfileBase(SQLModel):
    """
    Base model for user profile-related data, containing common fields shared across different profile types.
    """

    bio_recording_url: Optional[str] = None
    profile_picture_url: Optional[str] = None


class ProfileUpdate(ProfileBase):
    """
    Schema utilized to handle partial or full updates to a Profile object.
    All incoming attributes are explicitly configured as optional
    to support seamless HTTP PATCH workflows.
    """

    status: Optional[ProfileStatus] = None
    reason: Optional[RejectionReason] = None
    comment: Optional[str] = None


class Profile(ProfileBase, table=True):
    """
    Profile model representing a user's profile in the system, inheriting from ProfileBase and adding additional fields.
    """

    __tablename__ = "profiles"
    id: int = Field(default=None, primary_key=True)
    # Foreign key to the User model, establishing a one-to-one relationship between User and Profile. The user_id field is unique and cannot be null, ensuring that each profile is associated with exactly one user.
    user_id: int = Field(
        foreign_key="users.id", unique=True, index=True, ondelete="CASCADE"
    )
    age_category: AgeCategory = Field(
        sa_column=sa.Column(
            sa.Enum(AgeCategory, name="age_category_enum", create_type=False),
            nullable=False,
        )
    )

    status: ProfileStatus = Field(
        sa_column=sa.Column(
            sa.Enum(ProfileStatus, name="profile_status_enum", create_type=False),
            nullable=False,
        ),
        default=ProfileStatus.PENDING,
    )
    reason: Optional[RejectionReason] = Field(
        sa_type=sa.Enum(
            RejectionReason, name="rejection_reason_enum", create_type=False
        ),
        default=None,
        nullable=True,
    )
    comment: Optional[str] = Field(default=None)

    # Audit footprints
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

    # 1:1 Relationships (sa_relationship_kwargs enforces strict single-row mechanics)
    user: "User" = Relationship(
        back_populates="profile",
        sa_relationship_kwargs={
            "foreign_keys": "[Profile.user_id]",
            "lazy": "selectin",
        },
    )


##########################################################
# OUTGOING RESPONSE PAYLOAD DATA TRANSFER OBJECTS (DTOs) #
##########################################################


class ProfileResponse(ProfileBase):
    """
    Response DTO for profile updates by Admins
    """

    id: int
    age_category: AgeCategory
    status: ProfileStatus
    reason: Optional[RejectionReason] = None
    comment: Optional[str] = None
    date_created: datetime
    date_modified: datetime
    modified_by: Optional[int] = None
