###########################################################################################
# This script defines the user endpoints.

###########################################################################################

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_async_session
from app.models.user import (
    User,
    UserResponse,
    UserUpdate,
    UserSearchListResponse,
)
from app.models.profile import (
    Profile,
)
from app.core.utils.age_category import calculate_age_category
from app.models.enums import UserRole, ProfileStatus
from app.core.security import get_current_user, hash_password

users_router = APIRouter(prefix="/users", tags=["User Accounts"])


#############################################
#          GET USER BY USERNAME             #
#############################################
@users_router.get(
    "/search",
    response_model=UserSearchListResponse,
    summary="Search registered users by username",
)
async def get_users(
    username: str = Query(
        ..., min_length=3, description="Partial or incomplete username"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(
        20, ge=1, le=50, description="Maximum number of users to return"
    ),
    db: AsyncSession = Depends(get_async_session),
) -> UserSearchListResponse:
    """Search registered application users by their unique username handle.

    Executes a case-insensitive fuzzy pattern match across usernames. This lookup
    is hard-constrained to protect system metadata by entirely excluding
    administrative users from the returned visibility matrices.

    Args:
        username: The partial or full string search query parameters.
        page: Pagination selector representing the targeted page frame index.
        limit: The batch size constraint mapping max rows to deliver per query execution.
        db: An active asynchronous database session instance.
        current_user: The authenticated database user initiating the search filter.

    Returns:
        UserSearchListResponse: A dictionary payload envelope holding the light array
            of matched user summaries and a total count indicator.
    """
    # STandardize the lookup query text payload parameters
    search_query = f"%{username.strip().lower()}%"
    offset_delta = (page - 1) * limit

    filters = [
        User.username.ilike(search_query),
        User.is_active.is_(True),
        User.role != UserRole.ADMIN,
        Profile.status == ProfileStatus.APPROVED
    ]

    total_count = (await db.exec(select(func.count(User.id)).where(*filters))).one()
    users = (
        await db.exec(
            select(User)
            .join(Profile, Profile.user_id == User.id)
            .where(*filters)
            .order_by(User.username.asc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    return UserSearchListResponse(total_count=total_count, results=users)


#############################################
#             GET USER BY ID                #
#############################################


@users_router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve user by User ID",
)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> User:
    """Fetch a specific user account record along with its nested profile.

    Enforces data privacy by ensuring standard users can only fetch their own
    personal data profiles. Administrative accounts are granted global visibility
    to fetch any valid user ID record within the CRM persistence layer.

    Args:
        user_id: The primary key integer sequence identifying the target user.
        db: An active asynchronous database session instance provided by the pool.
        current_user: The authenticated database User making the request.

    Returns:
        User: The populated database User model containing nested profiles
            and metadata mapped cleanly to the UserResponse schema.

    Raises:
        HTTPException: 403 Forbidden if a standard user attempts to look up
            a database identity that does not match their own ID.
        HTTPException: 404 Not Found if the requested user ID is absent
            from the database.
    """
    # Users can look up themselves, but only Admins can query other users
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Insufficient account privileges.",
        )

    # Query user by ID
    user = await db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user record not found.",
        )

    # Return user
    return user


@users_router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user account and profile atomically (self service)",
)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> User:
    """Modify user account configurations and profile attributes partially (HTTP PATCH).

    Enforces strict data privacy. Standard accounts can only update their own
    matching user IDs. Administrative roles are granted global override parameters.
    This route explicitly bars standard users from privilege escalation or
    altering their own moderation status flags.

    Args:
        user_id: The primary key integer sequence identifying the target user.
        payload: An incoming schema holding optional account or profile parameters.
        db: An active asynchronous database session instance.
        current_user: The authenticated database User initiating the update.

    Returns:
        User: The fully updated database User model row containing hydrated
            and nested profile relationship maps.
    """
    is_owner = current_user.id == user_id
    is_admin = current_user.role == UserRole.ADMIN

    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action unauthorized. You can only modify your own account records.",
        )

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found."
        )

    incoming_data = payload.model_dump(exclude_unset=True)
    if not incoming_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No parameters supplied."
        )

    # Sanitize input parameters and check for uniqueness
    if "username" in incoming_data:
        clean_username = incoming_data["username"].strip().lower()
        if clean_username != user.username:
            username_exists = (
                await db.exec(select(User).where(User.username == clean_username))
            ).one_or_none()
            if username_exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username is already taken.",
                )
            incoming_data["username"] = clean_username

    if "email" in incoming_data:
        clean_email = incoming_data["email"].strip().lower()
        if clean_email != user.email:
            email_exists = (
                await db.exec(select(User).where(User.email == clean_email))
            ).one_or_none()
            if email_exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered.",
                )
            incoming_data["email"] = clean_email

    # Intercept and cryptographically has passwords
    if "password" in incoming_data:
        # Extract the plaintext password string from the dict to keep it out of bulk updates
        plaintext_password = incoming_data.pop("password")
        # Overwrite the actual database table column with the encrpypted string hash
        incoming_data["hashed_password"] = await hash_password(plaintext_password)

    # Segregate profile fields from core account parameters
    profile_fields = {"bio_recording_url", "profile_picture_url"}
    profile_update_data = {
        k: v for k, v in incoming_data.items() if k in profile_fields
    }
    user_update_data = {
        k: v for k, v in incoming_data.items() if k not in profile_fields
    }

    # Update age category bracket if birth date is changed/updated
    if "birth_date" in user_update_data:
        # Verify if the account is a standard user account
        if user.role == UserRole.USER:
            # Recalculate the age category bracket on the fly
            new_age_category = calculate_age_category(incoming_data["birth_date"])

            # Inject the new age category bracket into the profile_update_data
            profile_update_data["age_category"] = new_age_category

    runtime_now = datetime.now(timezone.utc)

    # Apply core user updates
    if user_update_data:
        user_update_data["date_modified"] = runtime_now
        user_update_data["modified_by"] = current_user.id
        user.sqlmodel_update(user_update_data)
        db.add(user)

    if profile_update_data:
        profile = user.profile
        if not profile:
            profile = Profile(
                user_id=user.id, age_category=calculate_age_category(user.birth_date)
            )
            db.add(profile)
            await db.flush()

        profile_update_data["date_modified"] = runtime_now
        profile_update_data["modified_by"] = current_user.id
        profile.sqlmodel_update(profile_update_data)
        db.add(profile)

    await db.commit()
    await db.refresh(user)

    return user


@users_router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a user account (Admin only)",
)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Permanently delete a user account and all associated profile assets.

    This route is strictly restricted to system administrators. Because of the
    underlying SQLAlchemy cascade constraints ('all, delete-orphan'), executing
    this drop will automatically trigger a cascading deletion across the
    user_profiles and user_tokens tables in PostgreSQL.

    Args:
        user_id: The primary key integer sequence identifying the target user to delete.
        db: An active asynchronous database session instance provided by the pool.
        current_user: The authenticated database User enforcing the deletion.

    Raises:
        HTTPException: 403 Forbidden if the calling user lacks an Admin role.
        HTTPException: 404 Not Found if the targeted user ID does not exist.

    Returns:
        None
    """
    # Enforce strict Admin RABC
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Account deletion is restricted to only administrators.",
        )

    # Fetch target user record to delete
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user record not found.",
        )

    await db.delete(user)
    await db.commit()

    return None
