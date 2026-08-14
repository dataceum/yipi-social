"""
This script defines the authentication endpoint
"""

import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import (
    User,
    UserCreate,
    UserLogin,
    UserResponse,
)

# Modle imports
from app.models.profile import ProfileBase, Profile
from app.models.enums import UserRole
from app.models.token import Token, TokenSetResponse, RefreshRequest

# Utils imports
from app.core.utils.age_category import (
    calculate_age_category,
)  # Utility to calculate age category bracket

# Core system imports
from app.core.security import (
    get_current_user,
    get_current_user_allow_inactive,
    hash_password,
    verify_password,
    create_access_token,
)
from app.core.db import get_async_session

auth_router = APIRouter(prefix="/auth", tags=["Authentication Layer"])


##################################################################################
#              Elevated User Signup/Registration API Endpoint                    #
##################################################################################
@auth_router.post(
    "/create_user",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user object without a complementary profile object. Only Admins allowd.",
)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Create a User object without provisioning a Profile container.

    This endpoint is strictly restricted to administrative users. It creates other (elevated) users. It validates account parameter uniqueness across usernames and email addresses before
    generating password hashes and committing records to the database.

    Args:
        payload: A validated incoming request schema containing registration metrics.
        db: An active asynchronous database session instance provided by the dependency pool.
        current_user: The authenticated administrative database User requesting execution.

    Returns:
        User: The fully instantiated database User model row containing generated primary key IDs and nested profile relationship maps.

    Raises:
        HTTPException: 403 Forbidden if the calling user lacks an Admin role.
        HTTPException: 409 Conflict if the requested username or email is already allocated within the persistence layer.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action restricted to only system administrators.",
        )

    # Sanitize inputs
    clean_username = payload.username.strip().lower()
    clean_email = payload.email.strip().lower()

    # Enforce username and email uniqueness
    username_exists = (
        await db.exec(select(User).where(User.username == clean_username))
    ).one_or_none()
    if username_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username is already taken."
        )

    email_exists = (
        await db.exec(select(User).where(User.email == clean_email))
    ).one_or_none()
    if email_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
        )

    assigned_role = (
        UserRole(payload.role) if hasattr(payload, "role") else UserRole.USER
    )

    encrypted_password = await hash_password(payload.password)
    age_category = calculate_age_category(payload.birth_date)

    # Construct the Core User Model using SQLModel's model_validate wrapper.
    # This automatically leaves the 'id' field out to let the database auto-increment sequence manage it.
    user = User.model_validate(
        payload,
        update={
            "username": clean_username,
            "email": clean_email,
            "hashed_password": encrypted_password,
            "role": assigned_role,
        },
    )
    db.add(user)

    # Flush the session to write the record to the database and securely generate the user
    # id (user.id)
    await db.flush()

    # Instantiate the complimentary user profile container if only it's a "user" role
    if user.role == UserRole.USER:
        user_profile = Profile(user_id=user.id, age_category=age_category)
        db.add(user_profile)

    # Commit the entire atomic transaction to the database
    await db.commit()

    # Refresh the user data to fully populate database properties for the response
    await db.refresh(user)

    # Return the user object
    return user


##################################################################################
#               Self-Service Signup/Registration API Endpoint                    #
##################################################################################


@auth_router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user object and a complementary profile object",
)
async def signup(
    payload: UserCreate,
    db: AsyncSession = Depends(get_async_session),
) -> User:
    """
    Create a User object and provision a blank Profile container atomically.

    This endpoint validates account parameter uniqueness across usernames and email addresses before
    generating password hashes and committing records to the database.

    Args:
        payload: A validated incoming request schema containing registration metrics.
        db: An active asynchronous database session instance provided by the dependency pool.
        current_user: The authenticated administrative database User requesting execution.

    Returns:
        User: The fully instantiated database User model row containing generated primary key IDs and nested profile relationship maps.

    Raises:
        HTTPException: 403 Forbidden if the calling user lacks an Admin role.
        HTTPException: 409 Conflict if the requested username or email is already allocated within the persistence layer.
    """

    # Sanitize inputs
    clean_username = payload.username.strip().lower()
    clean_email = payload.email.strip().lower()

    # Enforce username and email uniqueness
    username_exists = (
        await db.exec(select(User).where(User.username == clean_username))
    ).one_or_none()
    if username_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username is already taken."
        )

    email_exists = (
        await db.exec(select(User).where(User.email == clean_email))
    ).one_or_none()
    if email_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
        )

    # Encrypt the plaintext password using brcypt
    encrypted_password = await hash_password(payload.password)

    # Automatically calculate age category bracket
    age_category = calculate_age_category(payload.birth_date)

    #  Construct the Core User Model using SQLModel's model_validate wrapper.
    # This automatically leaves the 'id' field out to let the database auto-increment sequence manage it.
    user = User.model_validate(
        payload,
        update={
            "username": clean_username,
            "email": clean_email,
            "hashed_password": encrypted_password,
        },
    )
    db.add(user)

    # Flush the session to write the record to the database and securely generate the user
    # id (user.id)
    await db.flush()

    # Instantiate the dependent user profile using the freshly crafted user id
    user_profile = Profile(user_id=user.id, age_category=age_category)
    db.add(user_profile)

    # Commit the entire atomic transaction to the database
    await db.commit()

    # Refresh the user data to fully populate database properties for the response
    await db.refresh(user)

    # Return the user object
    return user


##################################################################################
#                          User Login API Endpiont                               #
##################################################################################
@auth_router.post("/login", response_model=TokenSetResponse)
async def login(
    request: Request,
    payload: UserLogin,
    db: AsyncSession = Depends(get_async_session),
) -> TokenSetResponse:
    """
    Validate user credentials, update user session/token, and provision both the login JWT session and the database tracking session.

    Args:
        request:

        payload:

        db: Database connection functionality

    Returns:
        TokenSetResponse:
            The generated JWT object
    """
    username = payload.username.strip().lower()
    statement = select(User).where(User.username == username)
    result = await db.exec(statement)
    user = result.one_or_none()

    # Verify user credentials
    if not user or not await verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is currently deactivated",
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )

    # Generate a high-entropy, cryptographically secure 64-character token string for the Refresh Session
    secure_refresh_string = secrets.token_urlsafe(64)

    # Record the Refresh Token into the database for state tracking
    token = Token(
        user_id=user.id,
        refresh_token=secure_refresh_string,
        user_agent=request.headers.get("user-agent"),
        client_ip=request.client.host if request.client else None,
    )

    db.add(token)
    await db.commit()

    # Return the unified session and database tokens back to the frontend
    return TokenSetResponse.model_validate(
        {
            "access_token": access_token,
            "refresh_token": secure_refresh_string,
            "token_type": "bearer",
        }
    )


##################################################################################
#                          User Logout API Endpiont                               #
##################################################################################
@auth_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidate active user session to log them out",
)
async def logout(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user_allow_inactive),
) -> None:
    """Permanently revoke a long-lived refresh token session inside the database log.

    This route accepts the active refresh token string from the frontend, queries
    the user_tokens table to ensure the tracking row belongs strictly to the
    authenticated user context, and sets its 'is_revoked' property to True.
    This instantly prevents future access token generation passes.

    Note: This endpoint allows inactive users to logout, so they can clean up
    their session tokens even if their account has been suspended.

    Args:
        payload: An incoming schema body carrying the refresh token string to terminate.
        db: An active asynchronous database session instance.
        current_user: The authenticated database User initiating the logout sequence.
            Can be inactive (suspended/locked) users.

    Raises:
        HTTPException: 404 Not Found if the targeted refresh token string does not
            exist or is already invalidated.
    """
    stmt = select(Token).where(
        Token.refresh_token == payload.refresh_token,
        Token.user_id == current_user.id,
        Token.is_revoked.is_(False),
    )
    stored_token: Token | None = (await db.exec(stmt)).one_or_none()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session already terminated, invalid or expired.",
        )

    stored_token.is_revoked = True

    db.add(stored_token)
    await db.commit()

    return None
