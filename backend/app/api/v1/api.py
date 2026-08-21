"""
This script gathers all the various endpoints into a unified router layer.

NOTE ON 3CX INTEGRATION:
  threecx_router is NOT included under api_router (/api/v1) because 3CX
  expects the exact path /api/method/smart_lookup_and_call_log — that
  path is baked into the CRM XML template and can't include a /v1 prefix.
  threecx_router carries its own /api/method prefix and must be included
  directly on the FastAPI app in main.py:

    app.include_router(api_router)
    app.include_router(threecx_router)   # ← separate, no /api/v1 prefix
"""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import auth_router
from app.api.v1.endpoints.users import users_router
from app.api.v1.endpoints.posts import posts_router
from app.api.v1.endpoints.comments import comments_router
from app.api.v1.endpoints.likes import likes_router
from app.api.v1.endpoints.media import media_router
from app.api.v1.endpoints.rooms import rooms_router
from app.api.v1.endpoints.reports import reports_router
from app.api.v1.endpoints.teams import teams_router
from app.api.v1.endpoints.calls import calls_router
from app.api.v1.endpoints.api_keys import api_keys_router
from app.api.v1.endpoints.threecx import (
    threecx_router,
)  # noqa: F401 — imported for re-export

api_router = APIRouter(prefix="/api/v1")

# Aggregate all resource endpoints
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(posts_router)
api_router.include_router(comments_router)
api_router.include_router(likes_router)
api_router.include_router(media_router)
api_router.include_router(rooms_router)
api_router.include_router(reports_router)
api_router.include_router(teams_router)
api_router.include_router(calls_router)
api_router.include_router(api_keys_router)

# threecx_router is exported for main.py to include separately — see note above.
