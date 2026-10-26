from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BulkTagsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_ids: list[int] = Field(min_length=1, max_length=200)
    add_tag_ids: list[int] = Field(default_factory=list, max_length=100)
    remove_tag_ids: list[int] = Field(default_factory=list, max_length=100)


class BulkMovePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_ids: list[int] = Field(min_length=1, max_length=200)
    target_folder_id: int


class BulkTrashPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_ids: list[int] = Field(min_length=1, max_length=200)


class BulkConvertPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_ids: list[int] = Field(min_length=1, max_length=200)


class BulkItemResult(BaseModel):
    asset_id: int
    ok: bool
    error: str | None = None


class BulkResult(BaseModel):
    ok_count: int
    failed_count: int
    items: list[BulkItemResult]
