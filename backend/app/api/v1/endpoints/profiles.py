###########################################################################################
# This script defines the user profile endpoints.

###########################################################################################

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.db import get_async_session
from app.models.profile import (
    Profile,
    ProfileResponse,
    ProfileUpdate,
)
from app.models.user import User
from app.models.enums import ProfileStatus, UserRole
from app.core.security import get_current_user

profiles_router = APIRouter(prefix="/profiles", tags=["User Profiles"])


@profiles_router.patch(
    "/moderate/{profile_id}",
    response_model=ProfileResponse,
    summary="Moderate user profile status (Amin only)",
)
async def moderate_profile(
    profile_id: int,
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Profile:
    """Moderate a user profile's status, reason, and comments.

    This path is strictly restricted to system administrators. If the profile status
    is transitioned to REJECTED or SUSPENDED, the system executes an automated
    Cascading Account Lock, shifting the associated User's 'is_active' attribute
    to False to secure application state immediately.

    Args:
        profile_id: The primary key sequence mapping the target Profile.
        payload: An administrative payload tracking status, reason, and moderation notes.
        db: An active asynchronous database session instance.
        current_user: The authenticated database user enforcing the moderation action.

    Returns:
        Profile: The modified database Profile model row containing
            new status keys and audit footprint mappings.
    """
    # Enfore strict admin RBAC
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Action restricted only to administrators.",
        )

    # Fetch the target profile
    profile = await db.get(Profile, profile_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user profile not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    runtime_now = datetime.now(timezone.utc)

    # Add auditing footprints
    update_data["date_modified"] = runtime_now
    update_data["modified_by"] = current_user.id

    # Enforce automated account security lock if profile status is set to REJECTED or SUSPENDED
    if payload.status in (ProfileStatus.REJECTED, ProfileStatus.SUSPENDED):
        user = await db.get(User, profile.user_id)
        # If the user's is_active flag is True, set to False
        if user and user.is_active:
            user.is_active = False
            user.date_modified = runtime_now
            user.modified_by = current_user.id
            db.add(user)

    # Commit all updates across both tables in a single atomic block
    profile.sqlmodel_update(update_data)
    db.add(profile)

    await db.commit()
    await db.refresh(profile)

    # Return the user profile object
    return profile


@profiles_router.delete(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete user profile container (Admin only)",
)
async def delete_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Permanently delete an isolated user profile without dropping the root account.

    This route is strictly restricted to system administrators. It purges the
    user_profiles row mapping, but preserves the parent account row inside the
    users table so history, authentication locks, and logs remain traceable.

    Args:
        profile_id: The primary key sequence mapping the target Profile to purge.
        db: An active asynchronous database session instance provided by the pool.
        current_user: The authenticated database user enforcing the deletion.

    Raises:
        HTTPException: 403 Forbidden if the calling user lacks an Admin role.
        HTTPException: 404 Not Found if the target profile record is completely missing.

    Returns:
        None
    """

    # Enforce strict Admin RABC
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Profile deletion is resctricted to only admins.",
        )

    # Get target user profile to delete
    profile = await db.get(Profile, profile_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user profile record not found.",
        )

    await db.delete(profile)
    await db.commit()

    return None
