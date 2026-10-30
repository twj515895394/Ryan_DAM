from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OpenReferencePayload(BaseModel):
    """开放接口参考图：base64 内嵌、已有资产、或历史生成结果，三选一。"""

    model_config = ConfigDict(extra="forbid")

    image_base64: str | None = None
    asset_id: int | None = None
    history_result_id: str | None = None
    role: Literal["reference", "mask"] = "reference"
    filename: str = "reference.png"

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "OpenReferencePayload":
        given = [self.image_base64, self.asset_id, self.history_result_id]
        provided = sum(1 for value in given if value not in (None, ""))
        if provided != 1:
            raise ValueError(
                "references 每项必须且只能提供 image_base64 / asset_id / history_result_id 之一"
            )
        return self


class OpenGeneratePayload(BaseModel):
    """一站式生图/图生图请求：缺省自动入库到『AI 生成』目录。"""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    negative_prompt: str | None = None
    task_type: Literal["auto", "image_generate", "image_edit"] = "auto"
    model_profile_id: int | None = None
    size: str | None = Field(default=None, pattern=r"^\d{3,5}x\d{3,5}$")
    aspect_ratio: str | None = None
    n: int = Field(default=1, ge=1, le=4)
    seed: int | None = None
    quality: str | None = None
    extra_params: dict[str, Any] | None = None
    request_timeout_s: int = Field(default=120, ge=10, le=900)
    references: list[OpenReferencePayload] = Field(default_factory=list)
    auto_import: bool = True
    target_folder_id: int | None = None
    wait: bool = False
    wait_timeout_s: int = Field(default=300, ge=5, le=900)


class OpenModelInfo(BaseModel):
    id: int
    name: str
    model_id: str
    provider_name: str
    capabilities: list[str]


class OpenDefaultModelInfo(BaseModel):
    model_profile_id: int | None = None
    name: str | None = None


class OpenInfoOut(BaseModel):
    product: str = "Ryan_DAM"
    version: str
    open_api_prefix: str
    open_base_urls: list[str]
    default_ai_folder: str
    default_models: dict[str, OpenDefaultModelInfo]
    models: list[OpenModelInfo]


class OpenResultOut(BaseModel):
    result_id: str
    idx: int
    mime_type: str
    width: int | None = None
    height: int | None = None
    size_bytes: int
    content_path: str
    imported_asset_id: int | None = None


class OpenTaskOut(BaseModel):
    task_id: str
    task_type: str
    status: str
    progress_pct: int | None = None
    prompt: str | None = None
    model_profile_id: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    results: list[OpenResultOut] = Field(default_factory=list)
