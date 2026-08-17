"""This script defines the User models and schemas for the application using SQLModel, which is a library that combines Pydantic and SQLAlchemy to provide a simple way to define database models with validation by emulating SQLAlchemy's ORM behavior."""

from datetime import datetime, date, timezone
from typing import Optional, List, Annotated, Union, TYPE_CHECKING
from pydantic import EmailStr
from sqlmodel import SQLModel, Field, Relationship
import sqlalchemy as sa
import phonenumbers
from pydantic_extra_types.phone_numbers import PhoneNumberValidator
from app.models.enums import (
    Gender,
    UserRole,
)

if TYPE_CHECKING:
    from app.models.profile import (
        Profile,
        ProfileBase,
        ProfileUpdate,
        ProfileResponse,
    )
    from app.models.token import Token

from app.models.profile import (
    Profile,
    ProfileBase,
    ProfileUpdate,
    ProfileResponse,
)
from app.models.token import Token
from app.models.post import Post

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

    username: str = Field(
        index=True,
        unique=True,
        min_length=3,
        max_length=20,
    )
    first_name: str = Field(
        min_length=2,
        max_length=50,
    )
    last_name: str = Field(
        min_length=2,
        max_length=50,
    )
    email: EmailStr = Field(index=True, unique=True)

    phone_number: E164PhoneNumber = Field(
        sa_column=sa.Column(sa.String(32), unique=True, index=True, nullable=False)
    )
    birth_date: date
    gender: Gender = Field(
        sa_column=sa.Column(sa.Enum(Gender, name="gender_enum", create_type=False))
    )


class UserLogin(SQLModel):
    """Schema used for authentication requests."""

    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8)


class CreateUser(UserBase, ProfileBase):
    """
    Model for creating a new user, extending UserBase and ProfileBase,
    and adding a password field. Since /auth/signup exclusively creates
    USER-role accounts, exposing bio_recording_url and profile_picture_url
    here lets a new user seed their profile at signup instead of starting blank.
    """

    password: str = Field(
        min_length=8, description="Password must be at least 8 characters long."
    )


class AdminCreateUser(UserBase):
    """
    Schema for administrator-issued account creation.

    Deliberately does NOT extend ProfileBase — ADMIN and MODERATOR accounts
    never have a Profile. Standard USER accounts must be created through the
    public /auth/signup endpoint, not this one.

    Only ever creates MODERATOR accounts — this endpoint intentionally has
    no path to provision an ADMIN account, even for an authenticated admin
    caller. ADMIN accounts are provisioned out-of-band.
    """

    password: str = Field(
        min_length=8, description="Password must be at least 8 characters long."
    )


class UpdateUser(ProfileBase):
    """
    Schema for standard-user self-service updates.

    Standard users may update their own account information and
    user-owned profile assets, but may not modify administrative
    profile state.
    """

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None


class AdminUpdateUser(ProfileUpdate):
    """
    Schema for administrative user and profile updates.

    Administrators may update standard user account fields,
    user profile assets, and administrative profile attributes.
    """

    # User account fields
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    phone_number: Optional[E164PhoneNumber] = None
    email: Optional[EmailStr] = None
    gender: Optional[Gender] = None
    birth_date: Optional[date] = None


class User(UserBase, table=True):
    """
    User model representing a user in the system, inheriting from UserBase and adding additional fields.
    """

    __tablename__ = "users"

    id: int = Field(default=None, primary_key=True)
    hashed_password: str
    is_active: bool = Field(default=False)
    role: UserRole = Field(
        sa_column=sa.Column(
            sa.Enum(UserRole, name="user_role_enum", create_type=False)
        ),
        default=UserRole.USER,
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

    # Profile Relationship
    profile: Optional["Profile"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "uselist": False,
            "cascade": "all, delete-orphan",
            "single_parent": True,
            "lazy": "selectin",
            "foreign_keys": "[Profile.user_id]",
        },
    )
    # Token Relationship
    tokens: list["Token"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "uselist": True,
            "lazy": "selectin",
            "foreign_keys": "[Token.user_id]",
        },
    )

    posts: list["Post"] = Relationship(
        back_populates="author",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[Post.author_id]",
            "lazy": "selectin",
        },
    )


##########################################################
# OUTGOING RESPONSE PAYLOAD DATA TRANSFER OBJECTS (DTOs) #
##########################################################
class UserResponse(SQLModel):
    """
    User response model returned for self-service user updates.
    """

    id: int
    username: str
    first_name: str
    last_name: str

    # Nested response model for the user's profile, including profile-related fields in the API response.
    profile: Optional[ProfileBase] = None


class AdminUserResponse(SQLModel):
    """
    User response model returned for user updates by Admins.
    """

    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    phone_number: str
    gender: Gender
    birth_date: date
    role: UserRole
    is_active: bool
    date_joined: datetime
    date_modified: datetime
    modified_by: Optional[int] = None

    # Nested response model for the user's profile, including profile-related fields in the API response.
    profile: Optional[ProfileResponse] = None

    # Nested response model for the user's profile, including profile-related fields in the API response.
    # profile: Optional[ProfileResponse] = None


class ModeratorUserResponse(SQLModel):
    """
    Response DTO for moderators reviewing accounts. Exposes enough to make
    an approve/reject decision — including profile status/reason/comment —
    without leaking contact-info PII (email, phone_number, birth_date,
    gender) that moderators don't need for content review.
    """

    id: int
    username: str
    first_name: str
    last_name: str

    profile: Optional[ProfileResponse] = None


class UserSearchList(SQLModel):
    """
    Lightweight user object optimized for public directory listings, follower feeds,
    and list components to maximize network bandwidth performance.
    """

    # Nesting the minimal avatar mapping wrapper safely
    total_count: int
    results: List[UserResponse]


class AdminUserSearchList(SQLModel):
    """Unified payload array structure for returning lightweight paginated search records."""

    total_count: int
    results: List[AdminUserResponse]


class ModeratorUserSearchList(SQLModel):
    """Payload array structure for returning moderator-level paginated search records."""

    total_count: int
    results: List[ModeratorUserResponse]
