from __future__ import annotations

import json
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.ai.model_config import AiDefaultBinding, AiModelProfile
from backend.app.models.ai.provider import AiProviderInstance
from backend.app.schemas.ai.model_config import (
    DefaultBindingPayload,
    DefaultBindingResponse,
    ModelProfileCreate,
    ModelProfileResponse,
    ModelProfileUpdate,
)


def _to_profile_response(profile: AiModelProfile) -> ModelProfileResponse:
    return ModelProfileResponse(
        id=profile.id,
        provider_id=profile.provider_id,
        model_id=profile.model_id,
        name=profile.name,
        adapter_kind=profile.adapter_kind,
        enabled=profile.enabled,
        capabilities=profile.capabilities,
        created_at=profile.created_at.isoformat() if profile.created_at else "",
        updated_at=profile.updated_at.isoformat() if profile.updated_at else "",
    )


def list_model_profiles(db: Session, provider_id: int | None = None) -> list[ModelProfileResponse]:
    stmt = select(AiModelProfile)
    if provider_id is not None:
        stmt = stmt.where(AiModelProfile.provider_id == provider_id)
    stmt = stmt.order_by(AiModelProfile.provider_id, AiModelProfile.name)
    rows = db.execute(stmt).scalars().all()
    return [_to_profile_response(r) for r in rows]


def get_model_profile(db: Session, profile_id: int) -> ModelProfileResponse:
    profile = db.get(AiModelProfile, profile_id)
    if not profile:
        raise ApiError(code="not_found", message=f"ModelProfile {profile_id} 不存在", status_code=404)
    return _to_profile_response(profile)


def create_model_profile(db: Session, provider_id: int, payload: ModelProfileCreate) -> ModelProfileResponse:
    provider = db.get(AiProviderInstance, provider_id)
    if not provider:
        raise ApiError(code="not_found", message=f"Provider {provider_id} 不存在", status_code=404)

    # Check unique (provider_id, model_id)
    existing = db.execute(
        select(AiModelProfile).where(
            AiModelProfile.provider_id == provider_id,
            AiModelProfile.model_id == payload.model_id.strip(),
        )
    ).scalar_one_or_none()
    if existing:
        raise ApiError(
            code="duplicate_model",
            message=f"该 Provider 下已存在 Model ID「{payload.model_id}」",
            status_code=409,
        )

    profile = AiModelProfile(
        provider_id=provider_id,
        model_id=payload.model_id.strip(),
        name=payload.name.strip(),
        adapter_kind=payload.adapter_kind,
        enabled=payload.enabled,
    )
    profile.capabilities = payload.capabilities
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _to_profile_response(profile)


def update_model_profile(db: Session, profile_id: int, payload: ModelProfileUpdate) -> ModelProfileResponse:
    profile = db.get(AiModelProfile, profile_id)
    if not profile:
        raise ApiError(code="not_found", message=f"ModelProfile {profile_id} 不存在", status_code=404)

    if payload.name is not None:
        profile.name = payload.name.strip()
    if payload.adapter_kind is not None:
        profile.adapter_kind = payload.adapter_kind
    if payload.enabled is not None:
        profile.enabled = payload.enabled
    if payload.capabilities is not None:
        profile.capabilities = payload.capabilities

    db.commit()
    db.refresh(profile)
    return _to_profile_response(profile)


def delete_model_profile(db: Session, profile_id: int) -> None:
    profile = db.get(AiModelProfile, profile_id)
    if not profile:
        raise ApiError(code="not_found", message=f"ModelProfile {profile_id} 不存在", status_code=404)
    db.delete(profile)
    db.commit()


# --- Default Bindings Strategy ---


def list_default_bindings(db: Session) -> list[DefaultBindingResponse]:
    stmt = (
        select(AiDefaultBinding, AiModelProfile, AiProviderInstance)
        .join(AiModelProfile, AiDefaultBinding.model_profile_id == AiModelProfile.id)
        .join(AiProviderInstance, AiModelProfile.provider_id == AiProviderInstance.id)
        .order_by(AiDefaultBinding.capability, AiDefaultBinding.scene)
    )
    rows = db.execute(stmt).all()
    results = []
    for binding, profile, provider in rows:
        results.append(
            DefaultBindingResponse(
                id=binding.id,
                capability=binding.capability,
                scene=binding.scene,
                model_profile_id=profile.id,
                model_name=profile.name,
                model_id=profile.model_id,
                provider_id=provider.id,
                provider_name=provider.name,
                created_at=binding.created_at.isoformat() if binding.created_at else "",
                updated_at=binding.updated_at.isoformat() if binding.updated_at else "",
            )
        )
    return results


def set_default_binding(db: Session, payload: DefaultBindingPayload) -> DefaultBindingResponse:
    profile = db.get(AiModelProfile, payload.model_profile_id)
    if not profile:
        raise ApiError(code="not_found", message=f"ModelProfile {payload.model_profile_id} 不存在", status_code=404)

    # Capability verification: the model profile must support this capability
    caps = profile.capabilities
    cap_conf = caps.get(payload.capability)
    if not cap_conf or not cap_conf.get("supported", True):
        raise ApiError(
            code="capability_unsupported",
            message=f"模型「{profile.name}」未声明支持能力「{payload.capability}」，无法设为默认模型",
            status_code=400,
        )

    binding = db.execute(
        select(AiDefaultBinding).where(
            AiDefaultBinding.capability == payload.capability,
            AiDefaultBinding.scene == payload.scene,
        )
    ).scalar_one_or_none()

    if binding:
        binding.model_profile_id = profile.id
    else:
        binding = AiDefaultBinding(
            capability=payload.capability,
            scene=payload.scene,
            model_profile_id=profile.id,
        )
        db.add(binding)

    db.commit()
    db.refresh(binding)
    provider = profile.provider

    return DefaultBindingResponse(
        id=binding.id,
        capability=binding.capability,
        scene=binding.scene,
        model_profile_id=profile.id,
        model_name=profile.name,
        model_id=profile.model_id,
        provider_id=provider.id if provider else 0,
        provider_name=provider.name if provider else "",
        created_at=binding.created_at.isoformat() if binding.created_at else "",
        updated_at=binding.updated_at.isoformat() if binding.updated_at else "",
    )


def resolve_model_for_capability(
    db: Session, capability: str, manual_profile_id: int | None = None, scene: str = "global"
) -> tuple[AiModelProfile, AiProviderInstance]:
    """Resolves model & provider following priority:

    Manual Selected > Scene Default > Global Default.
    """
    profile: AiModelProfile | None = None

    if manual_profile_id:
        profile = db.get(AiModelProfile, manual_profile_id)
        if not profile or not profile.enabled:
            raise ApiError(
                code="model_unavailable",
                message=f"指定模型 (ID {manual_profile_id}) 不可用或已停用",
                status_code=400,
            )

    if not profile and scene != "global":
        # Check scene default
        scene_binding = db.execute(
            select(AiDefaultBinding).where(
                AiDefaultBinding.capability == capability,
                AiDefaultBinding.scene == scene,
            )
        ).scalar_one_or_none()
        if scene_binding:
            p = db.get(AiModelProfile, scene_binding.model_profile_id)
            if p and p.enabled:
                profile = p

    if not profile:
        # Check global default
        global_binding = db.execute(
            select(AiDefaultBinding).where(
                AiDefaultBinding.capability == capability,
                AiDefaultBinding.scene == "global",
            )
        ).scalar_one_or_none()
        if global_binding:
            p = db.get(AiModelProfile, global_binding.model_profile_id)
            if p and p.enabled:
                profile = p

    if not profile:
        raise ApiError(
            code="no_model_configured",
            message=f"未找到可用的「{capability}」模型，请在设置中配置并设定默认模型",
            status_code=400,
        )

    provider = profile.provider
    if not provider or not provider.enabled:
        raise ApiError(
            code="provider_unavailable",
            message=f"模型关联的 Provider「{provider.name if provider else '未知'}」不存在或已停用",
            status_code=400,
        )

    return profile, provider
