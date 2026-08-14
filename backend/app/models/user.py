"""This script defines the User models and schemas for the application using SQLModel, which is a library that combines Pydantic and SQLAlchemy to provide a simple way to define database models with validation by emulating SQLAlchemy's ORM behavior."""

from datetime import datetime, date, timezone
from typing import Optional, List, Annotated, Union, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
import sqlalchemy as sa
from sqlalchemy.orm import Mapped
import phonenumbers
from pydantic_extra_types.phone_numbers import PhoneNumberValidator
from app.models.enums import (
    Gender,
    UserRole,
)

if TYPE_CHECKING:
    from app.models.profile import (
        Profile,
        ProfileResponse,
        ProfileBase,
    )
    from app.models.token import Token

from app.models.profile import (
    Profile,
    ProfileResponse,
    ProfileBase,
)
from app.models.token import Token

"""
Force-convert phone numbers into E164 format for database storage
"""
E164PhoneNumber = Annotated[
    Union[str, phonenumbers.PhoneNumber], PhoneNumberValidator(number_format="E164")
]


#####################################
#             USER LAYER            #
#####################################


class UserBase(SQLModel):
    """
    Base model for user-related data, containing common fields shared across different user types.
    """

    id: int = Field(default=None, primary_key=True)
    username: str = Field(
        index=True,
        unique=True,
        min_length=3,
        max_length=12,
    )
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)


class UserLogin(SQLModel):
    """Schema used for authentication requests."""

    username: str = Field(min_length=3, max_length=12)
    password: str = Field(min_length=8)


class UserCreate(UserBase):
    """
    Model for creating a new user, extending UserBase and adding a password field.
    """

    email: str = Field(index=True, unique=True)
    password: str = Field(
        min_length=8, description="Password must be at least 8 characters long."
    )
    gender: Gender
    role: UserRole = Field(default=UserRole.USER)


class UserUpdate(SQLModel):
    """
    Schema Schema for standard user self-service and full profile patch payloads
    """

    username: Optional[str] = Field(default=None, min_length=3, max_length=12)
    first_name: Optional[str] = Field(default=None, min_length=2, max_length=50)
    last_name: Optional[str] = Field(default=None, min_length=2, max_length=50)
    email: Optional[str] = Field(default=None)
    birth_date: Optional[date] = Field(default=None)
    phone_number: Optional[str] = Field(default=None, min_length=8, max_length=32)
    gender: Optional[Gender] = Field(default=None)
    is_active: Optional[bool] = Field(default=False)

    # Self-Service profile parameters allowed through the unified endpoint
    bio_recording_url: Optional[str] = Field(default=None, max_length=500)
    profile_picture_url: Optional[str] = Field(default=None, max_length=500)

    password: Optional[str] = Field(
        default=None,
        min_length=8,
        description="Optional plaintext string to modify password safely",
    )


class User(UserBase, table=True):
    """
    User model representing a user in the system, inheriting from UserBase and adding additional fields.
    """

    __tablename__ = "users"

    email: str = Field(index=True, unique=True)
    birth_date: date
    phone_number: str = Field(
        min_length=8,
        max_length=32,
        sa_column=sa.Column(sa.String(32), unique=True, index=True, nullable=False),
    )
    hashed_password: str
    is_active: bool = Field(default=False)
    role: UserRole = Field(
        sa_column=sa.Column(
            sa.Enum(UserRole, name="user_role_enum", create_type=False)
        ),
        default=UserRole.USER,
    )
    gender: Gender = Field(
        sa_column=sa.Column(sa.Enum(Gender, name="gender_enum", create_type=False))
    )

    # Audit footprints
    date_joined: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    date_modified: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    modified_by: Optional[int] = Field(default=None, foreign_key="users.id")

    # Relationships
    profile: Optional["Profile"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "uselist": False,
            "cascade": "all, delete-orphan",
            "foreign_keys": "[Profile.user_id]",
            "lazy": "selectin",
        },
    )

    tokens: list["Token"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "uselist": True,
            "lazy": "selectin",
            "foreign_keys": "[Token.user_id]",
        },
    )


##########################################################
# OUTGOING RESPONSE PAYLOAD DATA TRANSFER OBJECTS (DTOs) #
##########################################################


class UserResponse(UserBase):
    """
    Response model for user-related data, extending UserBase and adding additional fields for API responses.
    """

    email: str = Field(index=True, unique=True)
    phone_number: str
    date_joined: datetime
    date_modified: datetime
    modified_by: Optional[int]

    # Nested response model for the user's profile, including profile-related fields in the API response.
    profile: Optional[ProfileResponse] = None


class UserSummaryResponse(UserBase):
    """
    Lightweight user object optimized for public directory listings, follower feeds,
    and list components to maximize network bandwidth performance.
    """

    # Nesting the minimal avatar mapping wrapper safely
    profile: Optional[ProfileBase] = None


class UserSearchListResponse(SQLModel):
    """Unified payload array structure for returning lightweight paginated search records."""

    total_count: int
    results: List[
        "UserSummaryResponse"
    ]  # Returns only basic public card info (id, username, avatar)
