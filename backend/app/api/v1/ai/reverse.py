from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.schemas.ai.template import (
    ReverseTemplateCreate,
    ReverseTemplateOut,
    ReverseTemplateUpdate,
    SingleImageReverseRequest,
    SingleImageReverseResult,
)
from backend.app.services.ai import reverse_service

router = APIRouter(prefix="/ai/reverse", tags=["ai_reverse"])


@router.get("/templates", response_model=list[ReverseTemplateOut])
def list_templates(
    enabled_only: bool = Query(False, description="仅返回已启用的模板"),
    db: Session = Depends(get_db),
):
    """获取所有视觉提示词反推模板。"""
    templates = reverse_service.list_reverse_templates(db, enabled_only=enabled_only)
    return [
        ReverseTemplateOut(
            id=t.id,
            name=t.name,
            code=t.code,
            description=t.description,
            system_prompt=t.system_prompt,
            user_prompt_template=t.user_prompt_template,
            default_model_profile_id=t.default_model_profile_id,
            enabled=t.enabled,
            sort_order=t.sort_order,
            is_builtin=t.is_builtin,
            created_at=t.created_at.isoformat() if t.created_at else "",
            updated_at=t.updated_at.isoformat() if t.updated_at else "",
        )
        for t in templates
    ]


@router.post("/templates", response_model=ReverseTemplateOut, status_code=201)
def create_template(payload: ReverseTemplateCreate, db: Session = Depends(get_db)):
    """创建自定义视觉反推模板。"""
    t = reverse_service.create_reverse_template(db, payload)
    return ReverseTemplateOut(
        id=t.id,
        name=t.name,
        code=t.code,
        description=t.description,
        system_prompt=t.system_prompt,
        user_prompt_template=t.user_prompt_template,
        default_model_profile_id=t.default_model_profile_id,
        enabled=t.enabled,
        sort_order=t.sort_order,
        is_builtin=t.is_builtin,
        created_at=t.created_at.isoformat() if t.created_at else "",
        updated_at=t.updated_at.isoformat() if t.updated_at else "",
    )


@router.put("/templates/{template_id}", response_model=ReverseTemplateOut)
def update_template(template_id: int, payload: ReverseTemplateUpdate, db: Session = Depends(get_db)):
    """更新视觉反推模板。"""
    t = reverse_service.update_reverse_template(db, template_id, payload)
    return ReverseTemplateOut(
        id=t.id,
        name=t.name,
        code=t.code,
        description=t.description,
        system_prompt=t.system_prompt,
        user_prompt_template=t.user_prompt_template,
        default_model_profile_id=t.default_model_profile_id,
        enabled=t.enabled,
        sort_order=t.sort_order,
        is_builtin=t.is_builtin,
        created_at=t.created_at.isoformat() if t.created_at else "",
        updated_at=t.updated_at.isoformat() if t.updated_at else "",
    )


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    """删除自定义反推模板（系统内置模板不可删除）。"""
    reverse_service.delete_reverse_template(db, template_id)


@router.post("/assets/{asset_id}", response_model=SingleImageReverseResult)
async def reverse_single_image(
    asset_id: int,
    payload: SingleImageReverseRequest,
    db: Session = Depends(get_db),
):
    """对单张图片资产执行视觉反推。返回草稿与模型信息，不自动保存入库。"""
    return await reverse_service.reverse_single_image(db, asset_id, payload)
