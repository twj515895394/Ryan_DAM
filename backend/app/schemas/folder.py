from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FolderScope = Literal["general", "project"]


class FolderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    scope: FolderScope
    project_id: int | None = None
    parent_id: int | None = None


class FolderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: int | None = None
    locked: bool | None = None
    description: str | None = Field(default=None, max_length=2000)


class FolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope_type: str
    project_id: int | None
    parent_id: int | None
    sort_order: int
    locked: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class FolderNode(BaseModel):
    id: int
    name: str
    scope_type: str
    project_id: int | None
    parent_id: int | None
    sort_order: int
    locked: bool
    description: str | None
    children: list["FolderNode"] = []


class FolderStats(BaseModel):
    folder_id: int
    folder_name: str
    subfolder_count: int
    asset_count: int
    managed_asset_count: int
    external_asset_count: int

