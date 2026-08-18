"""
This script gathers all the various endpoints into a unified router layer
"""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import auth_router
from app.api.v1.endpoints.users import users_router
from app.api.v1.endpoints.posts import posts_router
from app.api.v1.endpoints.comments import comments_router
from app.api.v1.endpoints.likes import likes_router
from app.api.v1.endpoints.rooms import rooms_router
from app.api.v1.endpoints.reports import reports_router
from app.api.v1.endpoints.teams import teams_router
from app.api.v1.endpoints.calls import calls_router

api_router = APIRouter(prefix="/api/v1")

# Aggregate all resource endpionts
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(posts_router)
api_router.include_router(comments_router)
api_router.include_router(likes_router)
api_router.include_router(rooms_router)
api_router.include_router(reports_router)
api_router.include_router(teams_router)
api_router.include_router(calls_router)
