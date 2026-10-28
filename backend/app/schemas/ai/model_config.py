from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


AdapterKind = Literal["openai_standard", "openai_chat_markdown", "gemini_standard", "custom"]
AiCapability = Literal["text_optimize", "image_understand", "image_generate", "image_edit"]


class ParamSpec(BaseModel):
    name: str
    type: Literal["string", "integer", "number", "boolean", "enum"]
    required: bool = False
    default: Any = None
    enum_values: list[Any] | None = None
    min_val: float | None = None
    max_val: float | None = None
    adapter_key: str | None = None


class CapabilitySchema(BaseModel):
    supported: bool = True
    accepts_references: bool = False
    min_reference_count: int = 0
    max_reference_count: int = 0
    accepted_mime_types: list[str] = Field(default_factory=lambda: ["image/jpeg", "image/png", "image/webp"])
    max_file_bytes: int = 20 * 1024 * 1024  # 20MB
    supports_seed: bool = False
    supports_quality: bool = False
    supported_aspect_ratios: list[str] = Field(
        default_factory=lambda: ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"]
    )
    supported_sizes: list[str] = Field(
        default_factory=lambda: [
            "1024x1024", "1536x1536", "2048x2048",
            "1280x720", "1344x768", "1792x1024", "1920x1080", "2560x1440",
            "720x1280", "768x1344", "1024x1792", "1080x1920", "1440x2560",
            "1024x768", "1152x864", "1440x1080", "1600x1200", "2048x1536",
            "768x1024", "864x1152", "1080x1440", "1200x1600", "1536x2048",
            "1536x640", "2560x1080"
        ]
    )
    param_specs: list[ParamSpec] = Field(default_factory=list)


class ModelProfileCreate(BaseModel):
    model_id: str
    name: str
    adapter_kind: AdapterKind = "openai_standard"
    enabled: bool = True
    capabilities: dict[str, Any] = Field(default_factory=dict)


class ModelProfileUpdate(BaseModel):
    name: str | None = None
    adapter_kind: AdapterKind | None = None
    enabled: bool | None = None
    capabilities: dict[str, Any] | None = None


class ModelProfileResponse(BaseModel):
    id: int
    provider_id: int
    model_id: str
    name: str
    adapter_kind: str
    enabled: bool
    capabilities: dict[str, Any]
    created_at: str
    updated_at: str


class DefaultBindingPayload(BaseModel):
    capability: AiCapability
    scene: str = "global"
    model_profile_id: int


class DefaultBindingResponse(BaseModel):
    id: int
    capability: str
    scene: str
    model_profile_id: int
    model_name: str
    model_id: str
    provider_id: int
    provider_name: str
    created_at: str
    updated_at: str
