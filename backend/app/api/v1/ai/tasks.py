from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.core.errors import ApiError
from backend.app.models.ai.task import AiResult, AiTask, AiTaskItem, AiTaskReference
from backend.app.schemas.ai.task import (
    AiResultRead,
    AiTaskCancelResponse,
    AiTaskDetailRead,
    AiTaskItemRead,
    AiTaskListResponse,
    AiTaskReferenceRead,
    AiTaskSummaryRead,
    CommitBatchReversePayload,
    CommitBatchReverseResponse,
    StagedUploadOut,
    StagedUploadPayload,
    SubmitBatchReversePayload,
    SubmitImageGeneratePayload,
    UpdateTaskItemDraftPayload,
)
from backend.app.services.ai.generation_service import submit_image_generation
from backend.app.services.ai.reverse_service import (
    commit_batch_reverse_items,
    submit_batch_reverse,
)
from backend.app.services.ai.storage_service import stage_upload_file
from backend.app.services.ai.task_scheduler import get_task_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/tasks", tags=["ai-tasks"])


@router.post("/staging/upload", response_model=StagedUploadOut, status_code=201)
def upload_reference_image(
    payload: StagedUploadPayload,
    db: Annotated[Session, Depends(get_db)],
) -> StagedUploadOut:
    """上传或暂存本地参考图至 ai-history/staging 供生图或编辑参考。"""
    raw_bytes: bytes
    if payload.content_base64:
        try:
            b64_str = payload.content_base64
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            raw_bytes = base64.b64decode(b64_str)
        except Exception as exc:
            raise ApiError(code="invalid_base64", message=f"Base64 解析失败: {exc}", status_code=400)
    elif payload.file_path:
        p = Path(payload.file_path)
        if not p.exists() or not p.is_file():
            raise ApiError(code="file_not_found", message=f"指定的本地文件不存在: {payload.file_path}", status_code=404)
        raw_bytes = p.read_bytes()
    else:
        raise ApiError(code="missing_content", message="必须提供 content_base64 或 file_path", status_code=400)

    res = stage_upload_file(db=db, file_content=raw_bytes, filename=payload.filename or "reference.png")
    return StagedUploadOut(
        upload_id=res["upload_id"],
        filename=res["filename"],
        size_bytes=res["size_bytes"],
        width=res["width"],
        height=res["height"],
    )


@router.post("", response_model=AiTaskSummaryRead, status_code=201)
async def create_image_generate_task(
    payload: SubmitImageGeneratePayload,
    db: Annotated[Session, Depends(get_db)],
) -> AiTaskSummaryRead:
    """提交文生图/图像创作任务，加入异步受控并发队列。"""
    task = submit_image_generation(
        db=db,
        prompt=payload.prompt,
        model_profile_id=payload.model_profile_id,
        preset_id=payload.preset_id,
        params=payload.params,
        reference_asset_ids=payload.reference_asset_ids,
        references=payload.references,
        raw_user_request=payload.raw_user_request,
        task_type=payload.task_type,
        retry_of=payload.retry_of,
    )
    return AiTaskSummaryRead(
        id=task.id,
        task_type=task.task_type,
        provider_id=task.provider_id,
        provider_name=task.provider.name if task.provider else None,
        model_profile_id=task.model_profile_id,
        model_name=task.model_profile.name if task.model_profile else None,
        status=task.status,
        retry_of=task.retry_of,
        prompt_final=task.prompt_final,
        progress_pct=task.progress_pct,
        error_code=task.error_code,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
        finished_at=task.finished_at,
        items_count=0,
        results_count=0,
    )


@router.get("", response_model=AiTaskListResponse)
def list_tasks(
    db: Annotated[Session, Depends(get_db)],
    task_type: str | None = Query(None, description="任务类型过滤"),
    status: str | None = Query(None, description="任务状态过滤"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AiTaskListResponse:
    """获取 AI 执行任务列表（支持类型、状态过滤与分页）。"""
    query = db.query(AiTask)
    if task_type:
        query = query.filter(AiTask.task_type == task_type)
    if status:
        query = query.filter(AiTask.status == status)

    total = query.count()
    tasks = query.order_by(AiTask.created_at.desc()).offset(offset).limit(limit).all()

    items: list[AiTaskSummaryRead] = []
    for t in tasks:
        items.append(
            AiTaskSummaryRead(
                id=t.id,
                task_type=t.task_type,
                provider_id=t.provider_id,
                provider_name=t.provider.name if t.provider else None,
                model_profile_id=t.model_profile_id,
                model_name=t.model_profile.name if t.model_profile else None,
                status=t.status,
                retry_of=t.retry_of,
                prompt_final=t.prompt_final,
                progress_pct=t.progress_pct,
                error_code=t.error_code,
                error_message=t.error_message,
                created_at=t.created_at,
                updated_at=t.updated_at,
                finished_at=t.finished_at,
                items_count=len(t.items),
                results_count=len(t.results),
            )
        )

    return AiTaskListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{task_id}", response_model=AiTaskDetailRead)
def get_task_detail(
    task_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> AiTaskDetailRead:
    """获取单个 AI 任务的完整详情，包含子项、输入参考快照与生成结果。"""
    task = db.query(AiTask).filter(AiTask.id == task_id).first()
    if not task:
        raise ApiError(code="task_not_found", message=f"任务 #{task_id} 不存在", status_code=404)

    return AiTaskDetailRead(
        id=task.id,
        task_type=task.task_type,
        provider_id=task.provider_id,
        provider_name=task.provider.name if task.provider else None,
        model_profile_id=task.model_profile_id,
        model_name=task.model_profile.name if task.model_profile else None,
        preset_id=task.preset_id,
        status=task.status,
        retry_of=task.retry_of,
        idempotency_key=task.idempotency_key,
        prompt_final=task.prompt_final,
        raw_user_request=task.raw_user_request,
        params=task.params,
        external_handle=task.external_handle,
        error_code=task.error_code,
        error_message=task.error_message,
        progress_pct=task.progress_pct,
        created_at=task.created_at,
        updated_at=task.updated_at,
        finished_at=task.finished_at,
        items=[
            AiTaskItemRead(
                id=item.id,
                task_id=item.task_id,
                asset_id=item.asset_id,
                asset_name=item.asset.name if item.asset else None,
                current_prompt_text=item.asset.prompt_text if item.asset else None,
                status=item.status,
                draft_prompt_text=item.draft_prompt_text,
                prompt_revision_at_start=item.prompt_revision_at_start,
                error_code=item.error_code,
                error_message=item.error_message,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in task.items
        ],
        references=[
            AiTaskReferenceRead(
                id=ref.id,
                task_id=ref.task_id,
                seq=ref.seq,
                role=ref.role,
                source_kind=ref.source_kind,
                source_id=ref.source_id,
                snapshot_path=ref.snapshot_path,
                sha256=ref.sha256,
                created_at=ref.created_at,
            )
            for ref in task.references
        ],
        results=[
            AiResultRead(
                id=res.id,
                task_id=res.task_id,
                idx=res.idx,
                history_file_path=res.history_file_path,
                mime_type=res.mime_type,
                sha256=res.sha256,
                width=res.width,
                height=res.height,
                size_bytes=res.size_bytes,
                imported_asset_id=res.imported_asset_id,
                is_deleted=res.is_deleted,
                created_at=res.created_at,
            )
            for res in task.results
            if not res.is_deleted
        ],
    )


@router.post("/{task_id}/cancel", response_model=AiTaskCancelResponse)
async def cancel_task(
    task_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> AiTaskCancelResponse:
    """取消排队或请求中止执行中的 AI 任务。"""
    try:
        scheduler = get_task_scheduler()
    except RuntimeError:
        raise ApiError(code="scheduler_unavailable", message="任务调度器未就绪", status_code=503)

    cancelled = scheduler.request_cancel(task_id)
    task = db.query(AiTask).filter(AiTask.id == task_id).first()
    if not task:
        raise ApiError(code="task_not_found", message=f"任务 #{task_id} 不存在", status_code=404)

    return AiTaskCancelResponse(
        task_id=task_id,
        cancelled=cancelled,
        status=task.status,
    )


@router.post("/{task_id}/retry", response_model=AiTaskSummaryRead)
async def retry_task(
    task_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> AiTaskSummaryRead:
    """为失败、取消或需要恢复的任务安全创建关联的重试新任务。"""
    try:
        scheduler = get_task_scheduler()
    except RuntimeError:
        raise ApiError(code="scheduler_unavailable", message="任务调度器未就绪", status_code=503)

    new_task = scheduler.retry_task(db, task_id)
    if new_task.task_type in ("image_generate", "image_edit"):
        from backend.app.services.ai.generation_service import _make_generation_runner
        scheduler.dispatch(new_task.id, _make_generation_runner(scheduler.session_factory))
    elif new_task.task_type == "batch_reverse":
        from backend.app.services.ai.reverse_service import _make_batch_reverse_runner
        scheduler.dispatch(new_task.id, _make_batch_reverse_runner(scheduler.session_factory))

    return AiTaskSummaryRead(
        id=new_task.id,
        task_type=new_task.task_type,
        provider_id=new_task.provider_id,
        provider_name=new_task.provider.name if new_task.provider else None,
        model_profile_id=new_task.model_profile_id,
        model_name=new_task.model_profile.name if new_task.model_profile else None,
        status=new_task.status,
        retry_of=new_task.retry_of,
        prompt_final=new_task.prompt_final,
        progress_pct=new_task.progress_pct,
        error_code=new_task.error_code,
        error_message=new_task.error_message,
        created_at=new_task.created_at,
        updated_at=new_task.updated_at,
        finished_at=new_task.finished_at,
        items_count=len(new_task.items),
        results_count=len(new_task.results),
    )


@router.post("/batch-reverse", response_model=AiTaskSummaryRead, status_code=201)
async def create_batch_reverse_task(
    payload: SubmitBatchReversePayload,
    db: Annotated[Session, Depends(get_db)],
) -> AiTaskSummaryRead:
    """提交批量图片提示词反推任务。"""
    task = submit_batch_reverse(
        db=db,
        asset_ids=payload.asset_ids,
        template_id=payload.template_id,
        model_profile_id=payload.model_profile_id,
        custom_system_prompt=payload.custom_system_prompt,
        user_instruction=payload.user_instruction,
    )
    return AiTaskSummaryRead(
        id=task.id,
        task_type=task.task_type,
        provider_id=task.provider_id,
        provider_name=task.provider.name if task.provider else None,
        model_profile_id=task.model_profile_id,
        model_name=task.model_profile.name if task.model_profile else None,
        status=task.status,
        retry_of=task.retry_of,
        prompt_final=task.prompt_final,
        progress_pct=task.progress_pct,
        error_code=task.error_code,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
        finished_at=task.finished_at,
        items_count=len(task.items),
        results_count=0,
    )


@router.post("/{task_id}/commit-items", response_model=CommitBatchReverseResponse)
def commit_task_items(
    task_id: str,
    payload: CommitBatchReversePayload,
    db: Annotated[Session, Depends(get_db)],
) -> CommitBatchReverseResponse:
    """批量审核并采纳反推提示词至资产库（具备 CAS 保护与防静默覆盖保护）。"""
    res = commit_batch_reverse_items(
        db=db,
        task_id=task_id,
        item_ids=payload.item_ids,
        edited_drafts=payload.edited_drafts,
        allow_overwrite=payload.allow_overwrite,
    )
    return CommitBatchReverseResponse(
        committed_count=res["committed_count"],
        skipped_count=res["skipped_count"],
        conflict_count=res["conflict_count"],
        details=res["details"],
    )


@router.put("/{task_id}/items/{item_id}", response_model=AiTaskItemRead)
def update_task_item_draft(
    task_id: str,
    item_id: int,
    payload: UpdateTaskItemDraftPayload,
    db: Annotated[Session, Depends(get_db)],
) -> AiTaskItemRead:
    """修改待审核项的反推草稿内容。"""
    item = db.query(AiTaskItem).filter(AiTaskItem.task_id == task_id, AiTaskItem.id == item_id).first()
    if not item:
        raise ApiError(code="item_not_found", message=f"任务项 #{item_id} 不存在", status_code=404)

    item.draft_prompt_text = payload.draft_prompt_text.strip()
    db.commit()
    db.refresh(item)

    return AiTaskItemRead(
        id=item.id,
        task_id=item.task_id,
        asset_id=item.asset_id,
        asset_name=item.asset.name if item.asset else None,
        current_prompt_text=item.asset.prompt_text if item.asset else None,
        status=item.status,
        draft_prompt_text=item.draft_prompt_text,
        prompt_revision_at_start=item.prompt_revision_at_start,
        error_code=item.error_code,
        error_message=item.error_message,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )

