from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ImportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(min_length=1, max_length=5000)
    folder_id: int
    allow_duplicates: bool = False


class ImportJobItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_path: str
    status: str
    error_message: str | None
    asset_id: int | None


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    status: str
    target_folder_id: int | None
    total_count: int
    success_count: int
    skipped_count: int
    failed_count: int
    stage: str | None
    message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    items: list[ImportJobItemOut] = []
