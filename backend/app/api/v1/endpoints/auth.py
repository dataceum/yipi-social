"""
This script defines the authentication endpoint
"""

import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import (
    User,
    CreateUser,
    AdminCreateUser,
    UserLogin,
    UserResponse,
    AdminUserResponse,
)

# Modle imports
from app.models.profile import Profile
from app.models.team import Agent
from app.models.enums import UserRole
from app.models.token import (
    Token,
    TokenSetResponse,
    RefreshRequest,
)

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
#          Composite login response — carries CRM routing signal too            #
##################################################################################
class LoginResponse(TokenSetResponse):
    """
    Extends TokenSetResponse (access_token, refresh_token, token_type)
    rather than duplicating its fields — the token pair genuinely belongs
    to token.py, so this only adds what token.py has no business knowing:
    is_agent/agent_team_id.


        const { is_agent } = await login(...);
        window.location = is_agent ? '/crm' : '/app';

    is_agent/agent_team_id spare the frontend a second GET /users/me call
    immediately after login — /users/me still exists for re-checking
    status later in a session without forcing a re-login.
    """

    is_agent: bool
    agent_team_id: Optional[int] = None


##################################################################################
#              Elevated User Signup/Registration API Endpoint                    #
##################################################################################
@auth_router.post(
    "/create_user",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ADMIN or MODERATOR account. Admin only.",
)
async def create_user(
    payload: AdminCreateUser,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Create an elevated (ADMIN or MODERATOR) account with no Profile container.
    Defaults to a MODERATOR account.

    Strictly restricted to administrators. Rejects role=USER — standard
    accounts must go through /auth/signup so they always get a Profile.

    Raises:
        HTTPException: 403 if the caller isn't an ADMIN.
        HTTPException: 400 if payload.role == USER.
        HTTPException: 409 if username or email is already taken.

    Returns:
        User: Returns the created User object
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

    encrypted_password = await hash_password(payload.password)

    # Construct the Core User Model using SQLModel's model_validate wrapper.
    # This automatically leaves the 'id' field out to let the database auto-increment sequence manage it.
    user = User.model_validate(
        payload,
        update={
            "username": clean_username,
            "email": clean_email,
            "hashed_password": encrypted_password,
            "role": UserRole.MODERATOR,
            # Elevated accounts have no profile-approval workflow to flip this,
            # so they're active immediately. Flag if you want this to require
            # a separate manual activation step instead.
            "is_active": True,
        },
    )
    db.add(user)
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
    payload: CreateUser,
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

    Returns:
        User: A User object
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

    # Construct the Core User Model. role is intentionally left untouched here —
    # User.role already defaults to UserRole.USER, and CreateUser exposes no
    # role field, so this endpoint can never mint an elevated account.
    user = User.model_validate(
        payload,
        update={
            "username": clean_username,
            "email": clean_email,
            "hashed_password": encrypted_password,
        },
    )
    db.add(user)

    # Flush to generate user.id before the Profile FK needs it
    await db.flush()

    # Every account created here is USER-role, so a Profile is always provisioned
    user_profile = Profile(
        user_id=user.id,
        age_category=age_category,
        bio_recording_url=payload.bio_recording_url,
        profile_picture_url=payload.profile_picture_url,
    )
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
@auth_router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    payload: UserLogin,
    db: AsyncSession = Depends(get_async_session),
) -> LoginResponse:
    """
    Validate user credentials, update user session/token, and provision both the login JWT session and the database tracking session.

    Also resolves whether the authenticating user holds a CRM Agent record,
    so the frontend can route straight to the social network or CRM module
    off this single response — see LoginResponse.

    Args:
        request:
        payload:
        db: An asynchronous database sessoin

    Returns:
        LoginResponse: The generated JWT/refresh token pair, plus CRM
            agent status (is_agent, agent_team_id) for post-login routing.
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

    # Resolve CRM agent status for the frontend's post-login routing decision.
    agent = (await db.exec(select(Agent).where(Agent.user_id == user.id))).one_or_none()

    # Return the unified session tokens plus CRM routing signal to the frontend
    return LoginResponse(
        access_token=access_token,
        refresh_token=secure_refresh_string,
        token_type="bearer",
        is_agent=agent is not None,
        agent_team_id=agent.team_id if agent else None,
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
