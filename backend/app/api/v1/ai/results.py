from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.core.errors import ApiError
from backend.app.models.ai.task import AiResult, AiTask
from backend.app.schemas.ai.task import (
    AiResultListResponse,
    AiResultRead,
    AiResultTaskInfo,
    AiResultWithTaskRead,
    BatchImportResultsPayload,
    BatchImportResultsResponse,
    ImportResultItemOut,
    ImportResultPayload,
)
from backend.app.schemas.asset import AssetOut
from backend.app.services.ai.storage_service import (
    batch_import_results,
    delete_history_result,
    get_result_file_path,
    import_result_to_asset,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/results", tags=["ai-results"])


@router.get("", response_model=AiResultListResponse)
def list_results(
    db: Annotated[Session, Depends(get_db)],
    task_id: str | None = Query(None, description="按任务 ID 筛选"),
    task_type: str | None = Query(None, description="按任务类型筛选"),
    model_profile_id: int | None = Query(None, description="按模型筛选"),
    query: str | None = Query(None, description="按提示词关键词搜索"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AiResultListResponse:
    """获取永久 AI 生成历史列表（按生成时间倒序，支持任务、模型与关键词筛选）。"""
    q = db.query(AiResult).join(AiTask, AiResult.task_id == AiTask.id).filter(AiResult.is_deleted.is_(False))

    if task_id:
        q = q.filter(AiResult.task_id == task_id)
    if task_type:
        q = q.filter(AiTask.task_type == task_type)
    if model_profile_id:
        q = q.filter(AiTask.model_profile_id == model_profile_id)
    if query:
        q = q.filter(AiTask.prompt_final.ilike(f"%{query}%"))

    total = q.count()
    results = q.order_by(AiResult.created_at.desc()).offset(offset).limit(limit).all()

    items: list[AiResultWithTaskRead] = []
    for r in results:
        task_info = None
        if r.task:
            task_info = AiResultTaskInfo(
                task_type=r.task.task_type,
                provider_name=r.task.provider.name if r.task.provider else None,
                model_name=r.task.model_profile.name if r.task.model_profile else None,
                prompt_final=r.task.prompt_final,
            )
        items.append(
            AiResultWithTaskRead(
                id=r.id,
                task_id=r.task_id,
                idx=r.idx,
                history_file_path=r.history_file_path,
                mime_type=r.mime_type,
                sha256=r.sha256,
                width=r.width,
                height=r.height,
                size_bytes=r.size_bytes,
                imported_asset_id=r.imported_asset_id,
                is_deleted=r.is_deleted,
                created_at=r.created_at,
                task=task_info,
            )
        )

    return AiResultListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{result_id}", response_model=AiResultRead)
def get_result(
    result_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> AiResultRead:
    """获取单个生成结果的详情记录。"""
    result = db.query(AiResult).filter(AiResult.id == result_id, AiResult.is_deleted.is_(False)).first()
    if not result:
        raise ApiError(code="result_not_found", message=f"生成历史结果 #{result_id} 不存在", status_code=404)
    return AiResultRead.model_validate(result)


@router.get("/{result_id}/content")
def get_result_content(
    result_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    """经鉴权的安全历史文件流响应，返回图片文件。"""
    file_path, mime_type = get_result_file_path(db, result_id)
    return FileResponse(
        path=str(file_path),
        media_type=mime_type,
        filename=file_path.name,
    )


@router.delete("/{result_id}")
def delete_result(
    result_id: str,
    db: Annotated[Session, Depends(get_db)],
    confirm: bool = Query(False, description="破坏性操作确认"),
) -> dict[str, str]:
    """删除 AI 生成历史结果项（已入库正式资产独立保留不受影响）。"""
    if not confirm:
        raise ApiError(
            code="confirmation_required",
            message="删除生成历史是不可逆操作，需显式传入 confirm=true 参数",
            status_code=400,
        )

    delete_history_result(db, result_id, delete_physical=True)
    return {"id": result_id, "status": "deleted"}


@router.post("/{result_id}/import", response_model=AssetOut, status_code=201)
def import_single_result(
    result_id: str,
    payload: ImportResultPayload,
    db: Annotated[Session, Depends(get_db)],
) -> AssetOut:
    """将单张 AI 历史结果入库为系统主库托管资产（支持幂等）。"""
    from backend.app.api.v1.assets import _asset_out_with_tags

    asset, _ = import_result_to_asset(
        db=db,
        result_id=result_id,
        target_folder_id=payload.target_folder_id,
        custom_name=payload.custom_name,
    )
    return _asset_out_with_tags(db, asset)


@router.post("/batch-import", response_model=BatchImportResultsResponse)
def batch_import_results_endpoint(
    payload: BatchImportResultsPayload,
    db: Annotated[Session, Depends(get_db)],
) -> BatchImportResultsResponse:
    """批量将 AI 生成结果项入库为系统主库托管资产。"""
    items, total = batch_import_results(
        db=db,
        result_ids=payload.result_ids,
        target_folder_id=payload.target_folder_id,
    )
    return BatchImportResultsResponse(
        items=[ImportResultItemOut(**item) for item in items],
        total_imported=total,
    )
