from fastapi import APIRouter

from eyohe.api.v1 import auth, health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
