from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)


class TagUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str | None
    created_at: datetime
    updated_at: datetime


class TagWithCount(TagOut):
    asset_count: int


class AssetTagsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag_ids: list[int] = Field(max_length=100)
