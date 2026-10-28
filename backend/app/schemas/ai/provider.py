from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

ProviderFamily = Literal["openai_compatible", "openai_native", "gemini_native"]


class ProviderCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=128, description="Provider 实例名称")
    family: ProviderFamily = Field(default="openai_compatible", description="Provider 家族类型")
    base_url: str = Field(min_length=1, max_length=512, description="API 服务端点 Base URL")
    api_key: str = Field(min_length=1, max_length=1024, description="API Key 访问密钥（存入安全存储，不入库）")
    enabled: bool = Field(default=True, description="是否启用")
    settings: dict[str, Any] | None = Field(default=None, description="非敏感配置扩展参数")


class ProviderUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    family: ProviderFamily | None = Field(default=None)
    base_url: str | None = Field(default=None, min_length=1, max_length=512)
    api_key: str | None = Field(default=None, min_length=1, max_length=1024, description="留空则保持现有 Key")
    enabled: bool | None = Field(default=None)
    settings: dict[str, Any] | None = Field(default=None)


class ProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    family: str
    base_url: str
    enabled: bool
    has_api_key: bool
    masked_api_key: str
    settings: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ProviderTestPayload(BaseModel):
    model_id: str | None = Field(default=None, description="单模型测试时的模型 ID")
    capability: str | None = Field(default=None, description="指定单能力测试")
    capabilities: list[str] | None = Field(default=None, description="指定多能力测试列表")
    model_mapping: dict[str, str] | None = Field(default=None, description="各能力对应的模型 ID 字典")


class ProviderTestResponse(BaseModel):
    success: bool
    message: str
    results: dict[str, Any]


class RemoteModelItem(BaseModel):
    id: str = Field(description="模型 API 标识")
    name: str | None = Field(default=None, description="模型展示名称")
    description: str | None = Field(default=None, description="模型描述或归属说明")
