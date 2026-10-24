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
    created_at: datetime


class AssetPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AssetOut]
