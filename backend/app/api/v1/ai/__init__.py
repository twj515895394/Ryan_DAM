from backend.app.api.v1.ai.providers import router as providers_router
from backend.app.api.v1.ai.models import router as models_router
from backend.app.api.v1.ai.reverse import router as reverse_router
from backend.app.api.v1.ai.tasks import router as tasks_router
from backend.app.api.v1.ai.results import router as results_router
from backend.app.api.v1.ai.presets import router as presets_router

__all__ = [
    "providers_router",
    "models_router",
    "reverse_router",
    "tasks_router",
    "results_router",
    "presets_router",
]
