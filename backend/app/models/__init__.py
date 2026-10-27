"""SQLAlchemy ORM models. Import this package so Base.metadata is complete."""

from backend.app.models.ai.provider import AiProviderInstance
from backend.app.models.ai.model_config import AiModelProfile, AiDefaultBinding
from backend.app.models.ai.template import AiReverseTemplate, AiCreationPreset
from backend.app.models.ai.task import AiTask, AiTaskItem, AiTaskReference, AiResult
from backend.app.models.app_setting import AppSetting
from backend.app.models.asset import Asset
from backend.app.models.external_source import ExternalSource
from backend.app.models.folder import Folder
from backend.app.models.import_job import ImportJob, ImportJobItem
from backend.app.models.project import Project
from backend.app.models.tag import AssetTag, Tag

__all__ = [
    "AiProviderInstance",
    "AiModelProfile",
    "AiDefaultBinding",
    "AiReverseTemplate",
    "AiCreationPreset",
    "AiTask",
    "AiTaskItem",
    "AiTaskReference",
    "AiResult",
    "AppSetting",
    "Asset",
    "AssetTag",
    "ExternalSource",
    "Folder",
    "ImportJob",
    "ImportJobItem",
    "Project",
    "Tag",
]
