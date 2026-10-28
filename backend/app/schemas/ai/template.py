from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ReverseTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    code: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    system_prompt: str = Field(..., min_length=1)
    user_prompt_template: str | None = None
    default_model_profile_id: int | None = None
    enabled: bool = True
    sort_order: int = 0


class ReverseTemplateCreate(ReverseTemplateBase):
    pass


class ReverseTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    system_prompt: str | None = Field(default=None, min_length=1)
    user_prompt_template: str | None = None
    default_model_profile_id: int | None = None
    enabled: bool | None = None
    sort_order: int | None = None


class ReverseTemplateOut(ReverseTemplateBase):
    id: int
    is_builtin: bool
    created_at: str
    updated_at: str


class SingleImageReverseRequest(BaseModel):
    template_id: int | None = None
    model_profile_id: int | None = None
    language: Literal["zh", "en"] = "zh"
    custom_system_prompt: str | None = None
    user_instruction: str | None = None


class SingleImageReverseResult(BaseModel):
    asset_id: int
    reversed_prompt: str
    template_name: str
    model_id: str
    model_name: str
    provider_name: str
    has_conflict: bool = False
    current_asset_prompt: str | None = None
    current_asset_revision: int = 1


class CreationPresetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    code: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    creation_mode: str = "image_generate"
    system_rules: str = Field(..., min_length=1)
    default_model_profile_id: int | None = None
    default_params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    sort_order: int = 0


class CreationPresetCreate(CreationPresetBase):
    pass


class CreationPresetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    system_rules: str | None = Field(default=None, min_length=1)
    default_model_profile_id: int | None = None
    default_params: dict[str, Any] | None = None
    enabled: bool | None = None
    sort_order: int | None = None


class CreationPresetOut(CreationPresetBase):
    id: int
    is_builtin: bool
    created_at: str
    updated_at: str


class PromptOptimizeRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    preset_id: int | None = None
    model_profile_id: int | None = None
    custom_instruction: str | None = None


class PromptOptimizeResult(BaseModel):
    original_prompt: str
    optimized_prompt: str
    model_profile_id: int
    model_name: str
    provider_name: str
    diff_summary: str | None = None
