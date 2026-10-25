from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExternalSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_path: str = Field(min_length=1, max_length=1024)
    # 目标节点三选一（优先级：target_folder_id > target_project_id > 通用资产库顶层）
    target_folder_id: int | None = None
    target_project_id: int | None = None
    # True（默认）：在所选节点下新建与磁盘目录同名的目录并挂载内容；
    # False：内容直接索进所选目录（旧行为，必须给 target_folder_id）。
    create_mount_folder: bool = True
    display_name: str | None = Field(default=None, max_length=255)


class ExternalSourceOut(BaseModel):
    id: int
    root_path: str
    display_name: str | None
    target_folder_id: int
    target_folder_name: str | None
    mount_folder: bool = False
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


class UnlinkResult(BaseModel):
    removed: int
    mount_folder_removed: bool = False
