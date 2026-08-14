"""
This script gathers all the various endpoints into a unified router layer
"""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import auth_router
from app.api.v1.endpoints.users import users_router
from app.api.v1.endpoints.profiles import profiles_router

api_router = APIRouter(prefix="/api/v1")

# Aggregate all resource endpionts
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(profiles_router)
