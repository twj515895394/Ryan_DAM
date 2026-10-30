from fastapi import APIRouter

from backend.app.api.v1 import assets, bulk, external, folders, imports, projects, settings, tags, trash
from backend.app.api.v1 import open as open_api
from backend.app.api.v1.ai.providers import router as ai_providers_router
from backend.app.api.v1.ai.models import router as ai_models_router
from backend.app.api.v1.ai.reverse import router as ai_reverse_router
from backend.app.api.v1.ai.tasks import router as ai_tasks_router
from backend.app.api.v1.ai.results import router as ai_results_router
from backend.app.api.v1.ai.presets import router as ai_presets_router

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
api_router.include_router(ai_providers_router)
api_router.include_router(ai_models_router)
api_router.include_router(ai_reverse_router)
api_router.include_router(ai_tasks_router)
api_router.include_router(ai_results_router)
api_router.include_router(ai_presets_router)
api_router.include_router(open_api.router)
