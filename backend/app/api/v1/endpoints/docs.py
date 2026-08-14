# =====================================================================
# SECURE INTERACTIVE API DOCUMENTATION CHANNELS (ADMINS ONLY)
# =====================================================================

from datetime import datetime, timezone, timedelta
from html import escape

import jwt

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    Request,
    Form,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from sqlmodel import select

# User defined module imports
from app.core.config import settings
from app.core.db import async_session_maker
from app.core.security import (
    verify_password,
    SECURITY_KEY,
    ALGORITHM,
)
from app.models.user import User
from app.models.enums import UserRole

COOKIE_NAME = "docs_session"


# =====================================================================
# DOCUMENTATION SESSION AUTHENTICATION
# =====================================================================


async def get_user_from_cookie(request: Request) -> User:
    """
    Authenticate an administrator using the docs_session JWT cookie.

    This authentication mechanism is specifically for the interactive
    API documentation.

    Requirements:
        - Valid JWT
        - type == "docs_session"
        - User exists
        - User is active
        - User has ADMIN role
    """

    token_string = request.cookies.get(COOKIE_NAME)

    if not token_string:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized. Access denied.",
        )

    try:
        payload = jwt.decode(
            token_string,
            SECURITY_KEY,
            algorithms=[ALGORITHM],
        )

        user_id_str = payload.get("sub")
        token_type = payload.get("type")

        if token_type != "docs_session" or user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid documentation session.",
            )

        user_id = int(user_id_str)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Documentation session expired.",
        )

    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        print(f"❌ Docs Cookie JWT Decoding Failed: {exc}")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid documentation session.",
        )

    # ---------------------------------------------------------------
    # Fetch the authenticated user
    # ---------------------------------------------------------------

    async with async_session_maker() as db:
        user = await db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account not found.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive account.",
        )

    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Documentation access requires elevated privileges.",
        )

    return user


# =====================================================================
# SECURE DOCS ROUTES
# =====================================================================


def setup_secure_docs(app: FastAPI) -> None:
    """
    Register the secured Swagger UI documentation endpoints.

    Routes:

        GET  /docs
        POST /docs/login
        GET  /docs/logout
        GET  /openapi.json
    """

    # =================================================================
    # GET /docs
    # =================================================================

    @app.get("/docs", include_in_schema=False)
    async def get_swagger_docs(request: Request):

        # -------------------------------------------------------------
        # Authenticate documentation session
        # -------------------------------------------------------------

        try:
            await get_user_from_cookie(request)

        except HTTPException as exc:

            # Only authentication/authorization failures should
            # display the documentation login page.
            if exc.status_code not in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ):
                raise

            error_msg = escape(request.query_params.get("error", ""))

            error_alert = (
                f"""
                <div class="error-alert">
                    {error_msg}
                </div>
                """
                if error_msg
                else ""
            )

            # ---------------------------------------------------------
            # Documentation login page
            # ---------------------------------------------------------

            return HTMLResponse(
                content=f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">

                    <title>System Documentation Login</title>

                    <style>

                        body {{
                            font-family: Arial, sans-serif;
                            background: #f4f6f9;

                            display: flex;
                            justify-content: center;
                            align-items: center;

                            height: 100vh;
                            margin: 0;
                        }}

                        .login-card {{
                            background: white;

                            padding: 30px;

                            border-radius: 8px;

                            box-shadow:
                                0 4px 12px rgba(0,0,0,0.1);

                            width: 320px;
                        }}

                        h2 {{
                            margin-top: 0;
                            color: #333;
                            text-align: center;
                        }}

                        input {{
                            width: 100%;

                            padding: 10px;
                            margin: 10px 0;

                            border: 1px solid #ddd;
                            border-radius: 4px;

                            box-sizing: border-box;
                        }}

                        button {{
                            width: 100%;

                            padding: 10px;

                            background: #007bff;

                            border: none;

                            color: white;

                            border-radius: 4px;

                            font-size: 16px;

                            cursor: pointer;
                        }}

                        button:hover {{
                            background: #0056b3;
                        }}

                        .error-alert {{
                            background: #f8d7da;

                            color: #721c24;

                            border: 1px solid #f5c6cb;

                            padding: 10px;

                            border-radius: 4px;

                            margin-bottom: 15px;

                            text-align: center;
                        }}

                    </style>
                </head>

                <body>

                    <div class="login-card">

                        <h2>Admin Docs Portal</h2>

                        {error_alert}

                        <form
                            action="/docs/login"
                            method="post"
                        >

                            <input
                                type="text"
                                name="username"
                                placeholder="Username"
                                autocomplete="username"
                                required
                            >

                            <input
                                type="password"
                                name="password"
                                placeholder="Password"
                                autocomplete="current-password"
                                required
                            >

                            <button type="submit">
                                Unlock Documentation
                            </button>

                        </form>

                    </div>

                </body>
                </html>
                """,
            )

        # =============================================================
        # AUTHENTICATION SUCCEEDED
        # =============================================================

        swagger_response = get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - Swagger UI",
        )

        html = swagger_response.body.decode("utf-8")

        # =============================================================
        # DIRECT LOGOUT BUTTON INJECTION
        # =============================================================
        #
        # IMPORTANT:
        #
        # Swagger creates its .topbar dynamically with JavaScript.
        # Therefore we CANNOT reliably inject HTML into:
        #
        #     <div class="topbar">
        #
        # because that element does not exist yet in swagger_response.
        #
        # Instead, inject the button directly into the static HTML
        # before </body>.
        # =============================================================

        logout_button_html = """
        <a
            href="/docs/logout"
            class="docs-logout-btn"
            title="Logout from API documentation"
        >
            Logout from Docs
        </a>
        """

        logout_button_css = """
        <style>

            .docs-logout-btn {
                position: fixed;

                top: 10px;
                right: 20px;

                z-index: 99999;

                display: block;

                padding: 8px 16px;

                background: #f93e3e;
                color: #ffffff !important;

                border: 1px solid #d32f2f;

                border-radius: 4px;

                font-family: Arial, sans-serif;
                font-size: 14px;
                font-weight: bold;

                line-height: 1.4;

                text-decoration: none !important;

                cursor: pointer;

                box-shadow:
                    0 2px 6px rgba(0, 0, 0, 0.25);

                transition:
                    background-color 0.15s ease,
                    transform 0.15s ease;
            }

            .docs-logout-btn:hover {
                background: #d32f2f;
                color: #ffffff !important;

                text-decoration: none !important;

                transform: translateY(-1px);
            }

            .docs-logout-btn:active {
                transform: translateY(0);
            }

        </style>
        """

        # -------------------------------------------------------------
        # Inject CSS into <head>
        # -------------------------------------------------------------

        html = html.replace(
            "</head>",
            f"""
            {logout_button_css}
            </head>
            """,
            1,
        )

        # -------------------------------------------------------------
        # Inject logout button into static HTML
        # -------------------------------------------------------------

        html = html.replace(
            "</body>",
            f"""
            {logout_button_html}
            </body>
            """,
            1,
        )

        return HTMLResponse(
            content=html,
            status_code=status.HTTP_200_OK,
        )

    # =================================================================
    # POST /docs/login
    # =================================================================

    @app.post("/docs/login", include_in_schema=False)
    async def docs_login_endpoint(
        username: str = Form(...),
        password: str = Form(...),
    ):
        """
        Authenticate an administrator for the documentation portal.

        A dedicated docs_session JWT is created and stored in an
        HttpOnly cookie.
        """

        async with async_session_maker() as db:

            stmt = select(User).where(User.username == username.strip().lower())

            user = (await db.exec(stmt)).one_or_none()

        # -------------------------------------------------------------
        # Invalid credentials
        # -------------------------------------------------------------

        if not user or not await verify_password(
            password,
            user.hashed_password,
        ):
            return RedirectResponse(
                url="/docs?error=Invalid%20username%20or%20password",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        # -------------------------------------------------------------
        # Authorization
        # -------------------------------------------------------------

        if not user.is_active or user.role != UserRole.ADMIN:
            return RedirectResponse(
                url=("/docs?" "error=Forbidden%3A%20Elevated%20access%20required"),
                status_code=status.HTTP_303_SEE_OTHER,
            )

        # -------------------------------------------------------------
        # Create documentation session JWT
        # -------------------------------------------------------------

        token_expire = datetime.now(timezone.utc) + timedelta(hours=2)

        cookie_token = jwt.encode(
            {
                "sub": str(user.id),
                "type": "docs_session",
                "exp": int(token_expire.timestamp()),
            },
            SECURITY_KEY,
            algorithm=ALGORITHM,
        )

        # -------------------------------------------------------------
        # Redirect back to documentation
        # -------------------------------------------------------------

        response = RedirectResponse(
            url="/docs",
            status_code=status.HTTP_303_SEE_OTHER,
        )

        is_production = (
            getattr(
                settings,
                "ENVIRONMENT",
                "development",
            ).lower()
            == "production"
        )

        response.set_cookie(
            key=COOKIE_NAME,
            value=cookie_token,
            # JavaScript cannot access this cookie.
            httponly=True,
            # HTTPS only in production.
            secure=is_production,
            # Appropriate for the docs login flow.
            samesite="lax",
            # Make it available to /docs and API endpoints.
            path="/",
            # Explicitly expire the browser cookie after 2 hours.
            max_age=2 * 60 * 60,
        )

        return response

    # =================================================================
    # GET /docs/logout
    # =================================================================

    @app.get("/docs/logout", include_in_schema=False)
    async def docs_logout_endpoint():
        """
        Destroy the documentation session and return to the login page.
        """

        response = RedirectResponse(
            url="/docs",
            status_code=status.HTTP_303_SEE_OTHER,
        )

        response.delete_cookie(
            key=COOKIE_NAME,
            path="/",
        )

        return response

    # =================================================================
    # GET /openapi.json
    # =================================================================

    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_spec(
        user: User = Depends(get_user_from_cookie),
    ):
        """
        Return the OpenAPI schema only to authenticated administrators.
        """

        return get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
