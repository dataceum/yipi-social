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

    id: int = Field(default=None, primary_key=True)
    bio_recording_url: Optional[str] = Field(
        default=None, max_length=500, description="URL to the user's bio recording."
    )
    profile_picture_url: Optional[str] = Field(
        default=None, max_length=500, description="URL to the user's profile picture."
    )
    age_category: Optional[AgeCategory] = Field(default=None)


class ProfileCreate(ProfileBase):
    """
    Schema utilized during user registration workflows.
    Inherits all optional fields from ProfileBase, ensuring that profiles
    can be instantiated blank or with initial onboarding fields.
    """

    # Because the system automatically initializes a profile container during user registration with zero initial uploads required, this model acts as a pass-through layer for the endpoints
    pass


class ProfileUpdate(SQLModel):
    """
    Schema utilized to handle partial or full updates to a Profile object.
    All incoming attributes are explicitly configured as optional
    to support seamless HTTP PATCH workflows.
    """

    bio_recording_url: Optional[str] = Field(default=None)
    profile_picture_url: Optional[str] = Field(default=None)
    status: Optional[ProfileStatus] = Field(default=None)
    reason: Optional[RejectionReason] = Field(default=None)
    comment: Optional[str] = Field(default=None, nullable=True)


class Profile(ProfileBase, table=True):
    """
    Profile model representing a user's profile in the system, inheriting from ProfileBase and adding additional fields.
    """

    __tablename__ = "profiles"

    # Foreign key to the User model, establishing a one-to-one relationship between User and Profile. The user_id field is unique and cannot be null, ensuring that each profile is associated with exactly one user.
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
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
    comment: Optional[str] = Field(default=None, nullable=True)

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
    user: Optional["User"] = Relationship(
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
    Response DTO for user profile-related data returned via API calls
    """

    status: ProfileStatus
    reason: RejectionReason
    comment: Optional[str]
    date_created: datetime
    date_modified: datetime
    modified_by: Optional[int]
