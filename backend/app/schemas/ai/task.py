from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class AiTaskItemRead(BaseModel):
    id: int
    task_id: str
    asset_id: int | None = None
    asset_name: str | None = None
    current_prompt_text: str | None = None
    status: str
    draft_prompt_text: str | None = None
    prompt_revision_at_start: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiTaskReferenceRead(BaseModel):
    id: int
    task_id: str
    seq: int
    role: str | None = None
    source_kind: str
    source_id: str | None = None
    snapshot_path: str
    sha256: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiResultRead(BaseModel):
    id: str
    task_id: str
    idx: int
    history_file_path: str
    mime_type: str
    sha256: str | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int
    imported_asset_id: int | None = None
    is_deleted: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiTaskSummaryRead(BaseModel):
    id: str
    task_type: str
    provider_id: int | None = None
    provider_name: str | None = None
    model_profile_id: int | None = None
    model_name: str | None = None
    status: str
    retry_of: str | None = None
    prompt_final: str | None = None
    progress_pct: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
    items_count: int = 0
    results_count: int = 0


class AiTaskDetailRead(BaseModel):
    id: str
    task_type: str
    provider_id: int | None = None
    provider_name: str | None = None
    model_profile_id: int | None = None
    model_name: str | None = None
    preset_id: int | None = None
    status: str
    retry_of: str | None = None
    idempotency_key: str | None = None
    prompt_final: str | None = None
    raw_user_request: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    external_handle: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    progress_pct: int | None = None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
    items: list[AiTaskItemRead] = Field(default_factory=list)
    references: list[AiTaskReferenceRead] = Field(default_factory=list)
    results: list[AiResultRead] = Field(default_factory=list)


class AiTaskListResponse(BaseModel):
    items: list[AiTaskSummaryRead]
    total: int
    limit: int
    offset: int


class AiTaskCancelResponse(BaseModel):
    task_id: str
    cancelled: bool
    status: str


class AiResultTaskInfo(BaseModel):
    task_type: str
    provider_name: str | None = None
    model_name: str | None = None
    prompt_final: str | None = None


class AiResultWithTaskRead(BaseModel):
    id: str
    task_id: str
    idx: int
    history_file_path: str
    mime_type: str
    sha256: str | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int
    imported_asset_id: int | None = None
    is_deleted: bool
    created_at: datetime
    task: AiResultTaskInfo | None = None


class ReferenceItemPayload(BaseModel):
    source_kind: Literal["asset", "history_result", "local_upload"]
    source_id: str
    role: str = "reference"


class StagedUploadPayload(BaseModel):
    filename: str
    content_base64: str | None = None
    file_path: str | None = None


class StagedUploadOut(BaseModel):
    upload_id: str
    filename: str
    size_bytes: int
    width: int
    height: int


class SubmitImageGeneratePayload(BaseModel):
    task_type: Literal["image_generate", "image_edit"] = "image_generate"
    prompt: str = Field(min_length=1)
    model_profile_id: int | None = None
    preset_id: int | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    reference_asset_ids: list[int] = Field(default_factory=list)
    references: list[ReferenceItemPayload] = Field(default_factory=list)
    raw_user_request: str | None = None
    retry_of: str | None = None


class AiResultListResponse(BaseModel):
    items: list[AiResultWithTaskRead]
    total: int
    limit: int
    offset: int


class ImportResultPayload(BaseModel):
    target_folder_id: int | None = None
    custom_name: str | None = None


class BatchImportResultsPayload(BaseModel):
    result_ids: list[str] = Field(min_length=1)
    target_folder_id: int | None = None


class ImportResultItemOut(BaseModel):
    result_id: str
    asset_id: int | None = None
    status: str
    error_message: str | None = None


class BatchImportResultsResponse(BaseModel):
    items: list[ImportResultItemOut]
    total_imported: int


class SubmitBatchReversePayload(BaseModel):
    asset_ids: list[int] = Field(min_length=1)
    template_id: int | None = None
    model_profile_id: int | None = None
    language: Literal["zh", "en"] = "zh"
    custom_system_prompt: str | None = None
    user_instruction: str | None = None


class CommitBatchReversePayload(BaseModel):
    item_ids: list[int] = Field(min_length=1)
    edited_drafts: dict[int, str] = Field(default_factory=dict)
    allow_overwrite: bool = False


class CommitBatchReverseResponse(BaseModel):
    committed_count: int
    skipped_count: int
    conflict_count: int
    details: list[dict[str, Any]] = Field(default_factory=list)


class UpdateTaskItemDraftPayload(BaseModel):
    draft_prompt_text: str

