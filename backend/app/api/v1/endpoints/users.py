###########################################################################################
# This script defines the user endpoints.

###########################################################################################

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from typing import Union

from app.core.db import get_async_session
from app.models.user import (
    User,
    UserResponse,
    AdminUserResponse,
    UpdateUser,
    AdminUpdateUser,
    UserSearchList,
    AdminUserSearchList,
    ModeratorUserResponse,
    ModeratorUserSearchList,
)
from app.models.profile import Profile, ProfileUpdate
from app.core.utils.age_category import calculate_age_category
from app.models.enums import UserRole, ProfileStatus
from app.core.security import get_current_user, hash_password

users_router = APIRouter(prefix="/users", tags=["User Accounts"])


#############################################
#          GET USER BY USERNAME             #
#############################################
@users_router.get(
    "/search",
    response_model=AdminUserSearchList | ModeratorUserSearchList | UserSearchList,
    summary="Search active users by with approved profiles username, email or phone number",
)
async def get_users(
    query: str = Query(
        ...,
        min_length=3,
        description="Partial or incomplete username, email or phone number",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(
        20, ge=1, le=50, description="Maximum number of users to return"
    ),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> AdminUserSearchList | ModeratorUserSearchList | UserSearchList:
    """Search registered application users by their unique username handle.

    Executes a case-insensitive fuzzy pattern match across usernames, emails and phone numbers.
    This lookup is hard-constrained to protect system metadata by entirely excluding
    administrative users from the returned visibility matrices.

    Args:
        query: The partial or full string search query parameters.
        page: Pagination selector representing the targeted page frame index.
        limit: The batch size constraint mapping max rows to deliver per query execution.
        db: An active asynchronous database session instance.
        current_user: The authenticated database user initiating the search filter.

    Raises:
            HTTPException: 403 Forbidden if a standard user attempts to look up a database identity
            that does not match their own ID.
            HTTPException: 404 Not Found if the requested user ID is absent from the database.

    Returns:
        AdminUserSearchList | ModeratorSearchList| UserSearchList: A dictionary payload envelope holding the light array
        of matched user summaries and a total count indicator.
    """
    # Standardize the lookup query text payload parameters
    search_query = f"%{query.strip().lower()}%"
    offset_delta = (page - 1) * limit

    """
    TODO: Filter results based on age_category
    """
    base_search_filters = [
        User.username.ilike(search_query)
        | User.email.ilike(search_query)
        | User.phone_number.ilike(search_query)
    ]

    is_reviewer = current_user.role in {UserRole.ADMIN, UserRole.MODERATOR}

    if is_reviewer:
        # Admins and moderators see accounts across all profile statuses and
        # roles, for moderation purposes — no status/role/is_active restriction.
        filters = base_search_filters
    else:
        filters = base_search_filters + [
            User.role == UserRole.USER,
            Profile.status == ProfileStatus.APPROVED,
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

    if current_user.role == UserRole.ADMIN:
        return AdminUserSearchList(
            total_count=total_count,
            results=users,
        )

    if current_user.role == UserRole.MODERATOR:
        return ModeratorUserSearchList(
            total_count=total_count,
            results=users,
        )

    return UserSearchList(
        total_count=total_count,
        results=users,
    )


#############################################
#             GET USER BY ID                #
#############################################


@users_router.get(
    "/{user_id}",
    response_model=AdminUserResponse | ModeratorUserResponse | UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user by User ID",
)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> AdminUserResponse | ModeratorUserResponse | UserResponse:
    """Fetch a specific user account record along with its nested profile.

    Standard users may always view their own account. Viewing anyone else's
    account mirrors search visibility — only active USER-role accounts with
    an approved profile are visible; anything else returns 404. Admins and
    moderators have unrestricted visibility across all accounts.

    Args:
        user_id: The primary key integer sequence identifying the target user.
        db: An active asynchronous database session instance provided by the pool.
        current_user: The authenticated database User making the request.

    Raises:
        HTTPException: 404 Not Found if the requested user ID doesn't exist,
            or exists but isn't visible to the requesting user.

    Returns:
            AdminUserResponse |ModeratorUserResponse| UserResponse: A dictionary payload envelope holding the light array
            of matched user summaries and a total count indicator.
    """

    # Query user by ID
    user = await db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user record not found.",
        )

    is_privileged_reviewer = current_user.role in {UserRole.ADMIN, UserRole.MODERATOR}

    # Standard users may always view their own account regardless of status.
    # Looking up anyone else mirrors search visibility: only active USER-role
    # accounts with an approved profile are visible. Returns 404 rather than
    # 403 so existence of a pending/suspended/rejected account isn't leaked.
    if not is_privileged_reviewer and current_user.id != user_id:
        is_visible = (
            user.role == UserRole.USER
            and user.is_active
            and user.profile is not None
            and user.profile.status == ProfileStatus.APPROVED
        )
        if not is_visible:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user record not found.",
            )

    # Return response model based on the current user's role
    if current_user.role == UserRole.ADMIN:
        return AdminUserResponse.model_validate(user)

    if current_user.role == UserRole.MODERATOR:
        return ModeratorUserResponse.model_validate(user)

    return UserResponse.model_validate(user)


###########################################################
#  UPDATE USER AND PROFILE ATTRIBUTES BASED ON USER ROLE  #
###########################################################


@users_router.patch(
    "/{user_id}",
    response_model=AdminUserResponse | ModeratorUserResponse | UserResponse,
    summary="Update a user account and profile atomically (self service)",
)
async def update_user(
    user_id: int,
    payload: AdminUpdateUser,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> AdminUserResponse | ModeratorUserResponse | UserResponse:
    """Modify user account configurations and profile attributes partially of fully.

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
        AdminUserResponse or UserResonse: Depending on the role of the user making the update,
        the fully updated database AdminUserResponse or UserResponse model row containing
        hydrated and nested profile relationship maps.
    """

    USER_WRITABLE_FIELDS = frozenset(UpdateUser.model_fields)
    ADMIN_WRITABLE_FIELDS = frozenset(AdminUpdateUser.model_fields)
    PROFILE_PERSISTENCE_FIELDS = frozenset(ProfileUpdate.model_fields)
    USER_PERSISTENCE_FIELDS = frozenset(
        {
            "username",
            "first_name",
            "last_name",
            "phone_number",
            "email",
            "password",
            "gender",
            "birth_date",
        }
    )
    APPROVED_STATUS = ProfileStatus.APPROVED

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found."
        )

    is_owner = current_user.id == user_id
    is_admin = current_user.role == UserRole.ADMIN
    is_moderator = current_user.role == UserRole.MODERATOR
    can_administer_users = is_admin or is_moderator

    if not is_owner and not can_administer_users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify your own account, unless you have administrative privileges.",
        )

    # Moderators may administer their own account or standard USER accounts
    # only — not ADMIN or other MODERATOR accounts.
    if is_moderator and not is_owner and user.role != UserRole.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderators can only modify their own accounts and standard user accounts.",
        )

    # Check for allowed fields based on user role
    allowed_fields = (
        ADMIN_WRITABLE_FIELDS if can_administer_users else USER_WRITABLE_FIELDS
    )

    # Get the full compliment of the submitted fields in the payland
    submitted_fields = payload.model_fields_set

    # Get user-forbidden fields
    forbidden_fields = submitted_fields - allowed_fields

    if forbidden_fields:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You're not authorized to modify the following fields: "
            + ", ".join(sorted(forbidden_fields)),
        )

    incoming_data = payload.model_dump(exclude_unset=True)

    if not incoming_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No parameters supplied."
        )

    # Segregate user and profile fields from payload
    profile_update_data = {
        k: v for k, v in incoming_data.items() if k in PROFILE_PERSISTENCE_FIELDS
    }
    user_update_data = {
        k: v for k, v in incoming_data.items() if k in USER_PERSISTENCE_FIELDS
    }

    if profile_update_data and user.role != UserRole.USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile fields are not applicable to this account.",
        )

    try:
        # Sanitize input parameters and check for uniqueness
        """
        --- TODO: Comment out if you want to disable username updates
        """
        if "username" in user_update_data:
            clean_username = user_update_data["username"].strip().lower()

            if clean_username != user.username:
                username_exists = (
                    await db.exec(select(User).where(User.username == clean_username))
                ).one_or_none()

                if username_exists:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Username is already taken.",
                    )

                user_update_data["username"] = clean_username

        if "email" in user_update_data:
            clean_email = user_update_data["email"].strip().lower()

            if clean_email != user.email:
                email_exists = (
                    await db.exec(select(User).where(User.email == clean_email))
                ).one_or_none()

                if email_exists:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Email already registered.",
                    )

                user_update_data["email"] = clean_email

        # Intercept and cryptographically hash password
        if "password" in user_update_data:
            # Extract the plaintext password string from the dict to keep it out of bulk updates
            plaintext_password = user_update_data.pop("password")

            # Overwrite the actual database table column with the encrpypted string hash
            user_update_data["hashed_password"] = await hash_password(
                plaintext_password
            )

        # Check if payload contains "status", then activate/deactivate account accordingly
        if "status" in profile_update_data:
            if profile_update_data["status"] == APPROVED_STATUS:
                user_update_data["is_active"] = True
            else:
                user_update_data["is_active"] = False

        runtime_now = datetime.now(timezone.utc)

        # Apply core user updates
        if user_update_data:
            user_update_data["date_modified"] = runtime_now
            user_update_data["modified_by"] = current_user.id

            user.sqlmodel_update(user_update_data)
            db.add(user)

        # Apply profile updates
        if profile_update_data:
            profile = user.profile

            # If there's no Profile yet, get the birthdate from the payload and calculate the age_category, then create the Profile
            if not profile:
                # Use the new birth_date if it is part of this update;
                # otherwise use the user's existing birth_date.
                birth_date = user_update_data.get(
                    "birth_date",
                    user.birth_date,
                )

                profile_update_data["age_category"] = calculate_age_category(birth_date)

                profile = Profile(
                    user_id=user.id,
                    age_category=profile_update_data["age_category"],
                )

            profile_update_data["date_modified"] = runtime_now
            profile_update_data["modified_by"] = current_user.id

            profile.sqlmodel_update(profile_update_data)
            db.add(profile)

        await db.commit()
        await db.refresh(user)

    except Exception:
        await db.rollback()
        raise

    # Return response model based on user's role
    if current_user.role == UserRole.ADMIN:
        return AdminUserResponse.model_validate(user)

    if current_user.role == UserRole.MODERATOR:
        return ModeratorUserResponse.model_validate(user)

    return UserResponse.model_validate(user)


#########################################################################
# ADMIN ENDPOINT TO DELETE USER ACCOUNT, CASCADING TO ACCOUNT'S PROFILE #
#########################################################################
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
    """Permanently delete a user account and all associated profile and token assets.

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
