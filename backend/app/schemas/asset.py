from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    folder_id: int
    name: str
    extension: str | None
    asset_type: str
    size_bytes: int
    source_type: str
    thumbnail_status: str
    media_width: int | None
    media_height: int | None
    media_duration_ms: int | None
    file_path: str
    created_at: datetime
    updated_at: datetime


class AssetPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AssetOut]
