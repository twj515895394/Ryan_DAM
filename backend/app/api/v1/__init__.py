from fastapi import APIRouter

from backend.app.api.v1 import assets, bulk, external, folders, imports, projects, settings, tags, trash

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(projects.router)
api_router.include_router(folders.router)
api_router.include_router(assets.router)
api_router.include_router(imports.router)
api_router.include_router(tags.router)
api_router.include_router(bulk.router)
api_router.include_router(trash.router)
api_router.include_router(external.router)
api_router.include_router(settings.router)
