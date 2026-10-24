from fastapi import APIRouter

from backend.app.api.v1 import folders, projects, settings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(projects.router)
api_router.include_router(folders.router)
api_router.include_router(settings.router)
