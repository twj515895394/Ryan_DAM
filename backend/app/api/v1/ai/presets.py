from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.schemas.ai.template import (
    CreationPresetCreate,
    CreationPresetOut,
    CreationPresetUpdate,
    PromptOptimizeRequest,
    PromptOptimizeResult,
)
from backend.app.services.ai.preset_service import (
    create_creation_preset,
    delete_creation_preset,
    get_creation_preset,
    list_creation_presets,
    optimize_prompt,
    reset_creation_preset,
    update_creation_preset,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai-presets"])


def _preset_to_out(p) -> CreationPresetOut:
    return CreationPresetOut(
        id=p.id,
        name=p.name,
        code=p.code,
        description=p.description,
        creation_mode=p.creation_mode,
        system_rules=p.system_rules,
        default_model_profile_id=p.default_model_profile_id,
        default_params=p.default_params,
        is_builtin=p.is_builtin,
        enabled=p.enabled,
        sort_order=p.sort_order,
        created_at=p.created_at.isoformat() if p.created_at else "",
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
    )


@router.get("/ai/presets", response_model=list[CreationPresetOut])
def get_presets(
    db: Annotated[Session, Depends(get_db)],
    creation_mode: str | None = Query(None, description="创作模式过滤 (image_generate / image_edit)"),
    enabled_only: bool = Query(False, description="仅返回已启用的预设"),
) -> list[CreationPresetOut]:
    """获取 AI 创作场景预设列表。"""
    presets = list_creation_presets(db, creation_mode=creation_mode, enabled_only=enabled_only)
    return [_preset_to_out(p) for p in presets]


@router.get("/ai/presets/{preset_id}", response_model=CreationPresetOut)
def get_single_preset(
    preset_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> CreationPresetOut:
    """获取单个创作预设详情。"""
    preset = get_creation_preset(db, preset_id)
    return _preset_to_out(preset)


@router.post("/ai/presets", response_model=CreationPresetOut, status_code=201)
def add_preset(
    payload: CreationPresetCreate,
    db: Annotated[Session, Depends(get_db)],
) -> CreationPresetOut:
    """新建自定义创作预设。"""
    preset = create_creation_preset(db, payload)
    return _preset_to_out(preset)


@router.put("/ai/presets/{preset_id}", response_model=CreationPresetOut)
def edit_preset(
    preset_id: int,
    payload: CreationPresetUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CreationPresetOut:
    """更新创作预设。"""
    preset = update_creation_preset(db, preset_id, payload)
    return _preset_to_out(preset)


@router.delete("/ai/presets/{preset_id}", status_code=204, response_model=None)
def remove_preset(
    preset_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """删除自定义创作预设（系统内置预设不允许删除）。"""
    delete_creation_preset(db, preset_id)


@router.post("/ai/presets/{preset_id}/reset", response_model=CreationPresetOut)
def reset_preset(
    preset_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> CreationPresetOut:
    """将修改过的内置创作预设一键恢复为系统默认初始状态。"""
    preset = reset_creation_preset(db, preset_id)
    return _preset_to_out(preset)


@router.post("/ai/prompt/optimize", response_model=PromptOptimizeResult)
async def optimize_prompt_endpoint(
    payload: PromptOptimizeRequest,
    db: Annotated[Session, Depends(get_db)],
) -> PromptOptimizeResult:
    """调用大模型（text_chat）进行生图 Prompt 结构化扩写与润色。"""
    return await optimize_prompt(db, payload)
