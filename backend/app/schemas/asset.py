from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TagBrief(BaseModel):
    id: int
    name: str
    color: str | None


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    folder_id: int | None = None
    name: str
    extension: str | None
    asset_type: str
    size_bytes: int
    source_type: str
    thumbnail_status: str
    status: str = "active"
    media_width: int | None
    media_height: int | None
    media_duration_ms: int | None
    file_path: str
    created_at: datetime
    updated_at: datetime
    tags: list[TagBrief] = []
    has_prompt: bool = False


class AssetPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AssetOut]


class RenameAssetPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)


class MoveAssetPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder_id: int


class PromptPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_text: str | None = Field(default=None, max_length=100_000)


class AssetPromptOut(BaseModel):
    asset_id: int
    prompt_text: str | None
    has_prompt: bool
