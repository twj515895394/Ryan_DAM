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


class FolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope_type: str
    project_id: int | None
    parent_id: int | None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class FolderNode(BaseModel):
    id: int
    name: str
    scope_type: str
    project_id: int | None
    parent_id: int | None
    sort_order: int
    children: list["FolderNode"] = []
