"""
This module provides functions for password hashing, verification, and JWT token generation and decoding. It uses the bcrypt library for secure password hashing and the PyJWT library for handling JSON Web Tokens (JWTs). The security key and algorithm are loaded from the application settings, which are configured to read from environment variables or a .env file.
"""

from fastapi import Depends, HTTPException, Request, status
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi.security import OAuth2PasswordBearer
import asyncio
from pwdlib import PasswordHash
import jwt

from app.core.config import settings
from app.models.user import User
from app.models.enums import UserRole
from app.models.token import TokenData
from app.core.db import async_session_maker

SECURITY_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Token expiration time in minutes

COOKIE_NAME = "docs_session"

# ==============================================================
# OAuth2 / Swagger configuration
# ==============================================================
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/login",
    auto_error=False,
)

oauth2_scheme_required = OAuth2PasswordBearer(
    tokenUrl="/login",
    auto_error=True,
)


# ==============================================================
# Password hashing
# ==============================================================
password_manager = PasswordHash.recommended()


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
) -> User:
    """
    Authenticate the current API user.

    Authentication is attempted in this order:

    1. Normal Authorization: Bearer <access-token>
    2. docs_session HttpOnly cookie

    The docs_session cookie is only accepted when:

    - the JWT is valid
    - token type is exactly "docs_session"
    - the user exists
    - the user is active
    - the user is an administrator

    This allows authenticated administrators to use Swagger UI's
    "Try it out" functionality without manually clicking Authorize.

    Normal API clients continue to authenticate using Bearer tokens.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # ==========================================================
    # Try the normal Authorization: Bearer <token>
    # ==========================================================

    if token:
        try:
            payload = jwt.decode(
                token,
                SECURITY_KEY,
                algorithms=[ALGORITHM],
            )

            user_id_str = payload.get("sub")
            token_type = payload.get("type")

            # Normal API tokens must be access tokens.
            if token_type != "access" or user_id_str is None:
                raise credentials_exception

            user_id = int(user_id_str)

            async with async_session_maker() as db:
                user = await db.get(User, user_id)

            if user and user.is_active:
                return user

        except jwt.ExpiredSignatureError:
            # The Bearer token is expired. Continue below and see if this request has a valid docs_session cookie.
            pass

        except (
            jwt.InvalidTokenError,
            ValueError,
            TypeError,
        ):
            # Invalid Bearer token. Continue and see whether this request has a valid documentation session cookie.
            pass

    # ==========================================================
    # ADMIN DOCUMENTATION SESSION
    # =========================================================

    docs_token = request.cookies.get(COOKIE_NAME)

    if docs_token:

        try:
            payload = jwt.decode(
                docs_token,
                SECURITY_KEY,
                algorithms=[ALGORITHM],
            )

            user_id_str = payload.get("sub")
            token_type = payload.get("type")

            # docs_session must NEVER be treated as a normal API access token.
            if token_type != "docs_session" or user_id_str is None:
                raise credentials_exception

            user_id = int(user_id_str)

            async with async_session_maker() as db:
                user = await db.get(User, user_id)

            # docs_session is ONLY valid for active administrators.
            if user and user.is_active and user.role == UserRole.ADMIN:
                return user

        except jwt.ExpiredSignatureError:
            pass

        except (
            jwt.InvalidTokenError,
            ValueError,
            TypeError,
        ):
            pass

    # ==========================================================
    # Neither authentication method succeeded
    # ==========================================================

    raise credentials_exception


async def get_current_user_allow_inactive(
    token: str | None = Depends(oauth2_scheme_required),
) -> User:
    """
    Authenticate a user using a normal API access token.

    Unlike get_current_user(), this function intentionally does not
    require the user's account to be active.

    This is useful for operations such as logout or token/session
    cleanup where the user may have been deactivated after the token
    was issued.

    docs_session is intentionally NOT accepted here.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(
            token,
            SECURITY_KEY,
            algorithms=[ALGORITHM],
        )

        user_id_str = payload.get("sub")
        token_type = payload.get("type")

        # This dependency is specifically for normal API tokens.
        if token_type != "access" or user_id_str is None:
            raise credentials_exception

        user_id = int(user_id_str)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer error='invalid_token'"},
        )

    except (
        jwt.InvalidTokenError,
        ValueError,
        TypeError,
    ):
        raise credentials_exception

    async with async_session_maker() as db:
        user = await db.get(User, user_id)

    if not user:
        raise credentials_exception

    # Intentionally DO NOT check:
    #
    # if not user.is_active:
    #
    # because this dependency exists specifically to allow
    # identification of an inactive user.

    return user


async def hash_password(password: str) -> str:
    """
    Hash a password asynchronously.
    pwdlib automatically offloads this heavy operation to a background worker thread.

    Args:
        password (str): The plain text password to be hashed.

    Returns:
        str: The hashed password.
    """
    return await asyncio.to_thread(password_manager.hash, password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password asynchronously against its stored Argon2id hash string.

    Args:
        plain_password (str): The plain text password to be verified.
        hashed_password (str): The hashed password to compare against.

    Returns:
        bool: True if the passwords match, False otherwise.
    """

    return await asyncio.to_thread(
        password_manager.verify, plain_password, hashed_password
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token with the given data and expiration time.

    Args:
        data (dict): The data to be included in the token payload.
        expires_delta (Optional[timedelta]): The time delta for token expiration. If not provided, defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        str: The encoded JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": int(expire.timestamp()), "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECURITY_KEY, algorithm=ALGORITHM)
    return encoded_jwt
