from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TrashItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    asset_type: str
    size_bytes: int
    source_type: str
    deleted_at: datetime | None
    original_folder: str
    extension: str | None = None
    mime_type: str | None = None
    media_width: int | None = None
    media_height: int | None = None
    media_duration_ms: int | None = None
    thumbnail_status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TrashList(BaseModel):
    total: int
    items: list[TrashItem]


class TrashEmptyResult(BaseModel):
    removed: int
    failed: int = 0
