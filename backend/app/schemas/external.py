from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExternalSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_path: str = Field(min_length=1, max_length=1024)
    target_folder_id: int
    display_name: str | None = Field(default=None, max_length=255)


class ExternalSourceOut(BaseModel):
    id: int
    root_path: str
    display_name: str | None
    target_folder_id: int
    target_folder_name: str | None
    last_scan_at: datetime | None
    status: str
    asset_count: int
    missing_count: int


class ScanResult(BaseModel):
    added: int
    updated: int
    missing: int
    reactivated: int


class ExternalSourceCreated(BaseModel):
    source: ExternalSourceOut
    scan: ScanResult
