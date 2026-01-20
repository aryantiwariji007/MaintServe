from fastapi import APIRouter

from app.api.routes import admin, health, inference

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(inference.router, tags=["inference"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
