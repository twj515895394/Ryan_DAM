from __future__ import annotations

import json
from typing import Any
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.ai.model_config import AiModelProfile
from backend.app.models.ai.provider import AiProviderInstance
from backend.app.schemas.ai.provider import (
    ProviderCreatePayload,
    ProviderResponse,
    ProviderTestPayload,
    ProviderTestResponse,
    ProviderUpdatePayload,
    RemoteModelItem,
)
from backend.app.services.ai.credentials import CredentialManager
from backend.app.services.ai.protocol_poc import (
    CAPABILITY_IMAGE_EDIT,
    CAPABILITY_IMAGE_GENERATE,
    CAPABILITY_IMAGE_UNDERSTAND,
    CAPABILITY_TEXT_OPTIMIZE,
    normalize_base_url,
    probe_all_capabilities,
)


def _to_provider_response(instance: AiProviderInstance) -> ProviderResponse:
    secret = CredentialManager.get_credential(instance.credential_ref)
    masked = CredentialManager.mask_key(secret) if secret else ""
    settings_dict = json.loads(instance.settings_json) if instance.settings_json else None

    return ProviderResponse(
        id=instance.id,
        name=instance.name,
        family=instance.family,
        base_url=instance.base_url,
        enabled=instance.enabled,
        has_api_key=bool(secret),
        masked_api_key=masked,
        credential_masked=masked,
        settings=settings_dict,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


def list_providers(db: Session, enabled_only: bool = False) -> list[ProviderResponse]:
    if enabled_only:
        stmt = select(AiProviderInstance).where(AiProviderInstance.enabled.is_(True)).order_by(AiProviderInstance.id.asc())
    else:
        stmt = select(AiProviderInstance).order_by(AiProviderInstance.id.asc())

    instances = db.scalars(stmt).all()
    return [_to_provider_response(inst) for inst in instances]


def get_provider(db: Session, provider_id: int) -> ProviderResponse:
    instance = db.get(AiProviderInstance, provider_id)
    if instance is None:
        raise ApiError("not_found", f"AI Provider 实例不存在 (id={provider_id})", 404)
    return _to_provider_response(instance)


def get_provider_entity(db: Session, provider_id: int) -> AiProviderInstance:
    instance = db.get(AiProviderInstance, provider_id)
    if instance is None:
        raise ApiError("not_found", f"AI Provider 实例不存在 (id={provider_id})", 404)
    return instance


def get_provider_api_key(instance: AiProviderInstance) -> str:
    """Internal method for backend adapters to resolve the decrypted secret."""
    secret = CredentialManager.get_credential(instance.credential_ref)
    if not secret:
        raise ApiError("credential_missing", f"Provider「{instance.name}」未找到有效的安全凭据", 400)
    return secret


def create_provider(db: Session, payload: ProviderCreatePayload) -> ProviderResponse:
    name = payload.name.strip()
    existing = db.scalars(select(AiProviderInstance).where(AiProviderInstance.name == name)).first()
    if existing:
        raise ApiError("duplicate_name", f"Provider 实例名称「{name}」已存在。", 409)

    base_url = normalize_base_url(payload.base_url)
    ref_id = CredentialManager.save_credential(payload.api_key.strip())

    settings_str = json.dumps(payload.settings, ensure_ascii=False) if payload.settings else None
    instance = AiProviderInstance(
        name=name,
        family=payload.family,
        base_url=base_url,
        credential_ref=ref_id,
        enabled=payload.enabled,
        settings_json=settings_str,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return _to_provider_response(instance)


def update_provider(db: Session, provider_id: int, payload: ProviderUpdatePayload) -> ProviderResponse:
    instance = db.get(AiProviderInstance, provider_id)
    if instance is None:
        raise ApiError("not_found", f"AI Provider 实例不存在 (id={provider_id})", 404)

    if payload.name is not None:
        name = payload.name.strip()
        if name != instance.name:
            existing = db.scalars(
                select(AiProviderInstance).where(
                    AiProviderInstance.name == name,
                    AiProviderInstance.id != provider_id,
                )
            ).first()
            if existing:
                raise ApiError("duplicate_name", f"Provider 实例名称「{name}」已存在。", 409)
            instance.name = name

    if payload.family is not None:
        instance.family = payload.family

    if payload.base_url is not None:
        instance.base_url = normalize_base_url(payload.base_url)

    if payload.enabled is not None:
        instance.enabled = payload.enabled

    if payload.settings is not None:
        instance.settings_json = json.dumps(payload.settings, ensure_ascii=False)

    if payload.api_key is not None and payload.api_key.strip():
        # Update encrypted credential
        instance.credential_ref = CredentialManager.save_credential(
            payload.api_key.strip(), ref_id=instance.credential_ref
        )

    db.commit()
    db.refresh(instance)
    return _to_provider_response(instance)


def delete_provider(db: Session, provider_id: int) -> None:
    instance = db.get(AiProviderInstance, provider_id)
    if instance is None:
        raise ApiError("not_found", f"AI Provider 实例不存在 (id={provider_id})", 404)

    CredentialManager.delete_credential(instance.credential_ref)
    db.delete(instance)
    db.commit()


def test_provider_connection(
    db: Session,
    provider_id: int,
    payload: ProviderTestPayload,
    *,
    client: httpx.Client | None = None,
) -> ProviderTestResponse:
    instance = db.get(AiProviderInstance, provider_id)
    if instance is None:
        raise ApiError("not_found", f"AI Provider 实例不存在 (id={provider_id})", 404)

    secret = CredentialManager.get_credential(instance.credential_ref)
    if not secret:
        raise ApiError("credential_missing", "Provider 未配置有效 API Key", 400)

    # Resolve capability mapping
    mapping: dict[str, str] = {}
    if payload.model_mapping:
        mapping.update(payload.model_mapping)

    if payload.model_id:
        # If single model provided without mapping, apply to specified capability or all
        cap = payload.capability or CAPABILITY_TEXT_OPTIMIZE
        mapping[cap] = payload.model_id

    managed_client = client or httpx.Client()
    try:
        # Fallback default probe if no model mapping given
        if not mapping:
            # 1. 优先使用数据库中该 Provider 已经配置的模型
            configured_models = db.scalars(
                select(AiModelProfile).where(
                    AiModelProfile.provider_id == provider_id,
                    AiModelProfile.enabled.is_(True),
                )
            ).all()
            for cm in configured_models:
                caps_dict = json.loads(cm.capabilities_json) if cm.capabilities_json else {}
                for cap_name, cap_meta in caps_dict.items():
                    if isinstance(cap_meta, dict) and cap_meta.get("supported"):
                        if cap_name not in mapping:
                            mapping[cap_name] = cm.model_id

        if not mapping:
            # 2. 动态探测 Provider 远端实际支持的模型，避免硬编码模型 ID 导致第三方网关报错
            try:
                remote_models = fetch_remote_models(db, provider_id, client=managed_client)
            except Exception:
                remote_models = []

            if remote_models:
                text_candidate: str | None = None
                image_candidate: str | None = None
                for rm in remote_models:
                    rid = rm.id.lower()
                    if any(kw in rid for kw in ("image", "imagine", "dall-e", "flux", "draw")) and not image_candidate:
                        image_candidate = rm.id
                    elif not any(kw in rid for kw in ("image", "imagine", "video", "tts", "voice", "audio")) and not text_candidate:
                        text_candidate = rm.id

                if text_candidate:
                    mapping[CAPABILITY_TEXT_OPTIMIZE] = text_candidate
                if image_candidate:
                    mapping[CAPABILITY_IMAGE_GENERATE] = image_candidate

        if not mapping:
            # 3. 终极保底
            mapping[CAPABILITY_TEXT_OPTIMIZE] = "gpt-4o-mini"

        caps_to_test = payload.capabilities or list(mapping.keys())

        raw_results = probe_all_capabilities(
            managed_client,
            instance.base_url,
            secret,
            mapping,
            capabilities=caps_to_test,
        )
        serializable_results = {k: v.to_dict() for k, v in raw_results.items()}
        any_success = any(v.supported for v in raw_results.values())
        msg = "部分或全部能力测试通过" if any_success else "所有被测能力均未通过测试"
        return ProviderTestResponse(
            success=any_success,
            message=msg,
            results=serializable_results,
        )
    finally:
        if client is None:
            managed_client.close()


def fetch_remote_models(
    db: Session,
    provider_id: int,
    client: httpx.Client | None = None,
) -> list[RemoteModelItem]:
    instance = db.get(AiProviderInstance, provider_id)
    if instance is None:
        raise ApiError("not_found", f"AI Provider 实例不存在 (id={provider_id})", 404)

    secret = CredentialManager.get_credential(instance.credential_ref) or ""

    base_url = instance.base_url.rstrip("/")
    # 构建候选路径以优雅兼容带 /v1 与不带 /v1 的网关配置
    candidate_urls: list[str] = [f"{base_url}/models"]
    if not base_url.endswith("/v1"):
        candidate_urls.append(f"{base_url}/v1/models")
    elif base_url.endswith("/v1"):
        candidate_urls.append(f"{base_url[:-3]}/models")

    headers: dict[str, str] = {"Accept": "application/json"}
    params: dict[str, str] = {}

    if instance.family == "gemini_native":
        if secret:
            headers["x-goog-api-key"] = secret
            params["key"] = secret
    else:
        if secret:
            headers["Authorization"] = f"Bearer {secret}"

    managed_client = client or httpx.Client()
    try:
        last_res: httpx.Response | None = None
        last_exc: Exception | None = None
        working_url: str | None = None

        for target_url in candidate_urls:
            try:
                res = managed_client.get(target_url, headers=headers, params=params, timeout=15.0)
                last_res = res
                if res.status_code == 200:
                    working_url = target_url
                    break
            except Exception as exc:
                last_exc = exc
                continue

        if working_url is None:
            if last_res is not None:
                preview = last_res.text[:200] if last_res.text else ""
                raise ApiError(
                    "remote_models_failed",
                    f"获取模型列表失败 (HTTP {last_res.status_code}): {preview}",
                    400,
                )
            raise ApiError("remote_models_failed", f"连接 Provider 服务失败: {last_exc}", 400) from last_exc

        # 若发现缺少 /v1 导致必须走 /v1/models 才能连通，自动为 Provider 自愈补全 /v1
        if working_url.endswith("/v1/models") and not instance.base_url.rstrip("/").endswith("/v1"):
            instance.base_url = f"{instance.base_url.rstrip('/')}/v1"
            db.commit()
            db.refresh(instance)

        res = last_res

        try:
            data = res.json()
        except Exception as exc:
            raise ApiError("remote_models_failed", "Provider 返回内容非有效 JSON", 400) from exc

        raw_items: list[dict[str, Any] | str] = []
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                raw_items = data["data"]
            elif "models" in data and isinstance(data["models"], list):
                raw_items = data["models"]
        elif isinstance(data, list):
            raw_items = data

        parsed_models: dict[str, RemoteModelItem] = {}
        for item in raw_items:
            if isinstance(item, dict):
                # 兼容 Gemini 格式 "models/gemini-1.5-flash" 与 OpenAI 格式 "gpt-4o"
                raw_id = item.get("id") or item.get("name") or ""
                if not raw_id:
                    continue
                model_id = str(raw_id).strip()
                if model_id.startswith("models/"):
                    model_id = model_id[len("models/") :]

                display_name = item.get("displayName") or item.get("name") or model_id
                desc = item.get("description") or item.get("owned_by")

                if model_id and model_id not in parsed_models:
                    parsed_models[model_id] = RemoteModelItem(
                        id=model_id,
                        name=str(display_name),
                        description=str(desc) if desc else None,
                    )
            elif isinstance(item, str):
                model_id = item.strip()
                if model_id and model_id not in parsed_models:
                    parsed_models[model_id] = RemoteModelItem(id=model_id, name=model_id)

        # 排序：字母序
        result = sorted(parsed_models.values(), key=lambda x: x.id.lower())
        return result
    finally:
        if client is None:
            managed_client.close()

