"""对外免鉴权开放接口（个人局域网跨机调用）。

供其他项目复用本应用的 AI 生图/图生图能力：跟随项目配置的默认模型，
结果默认自动入库到『AI 生成』目录。见 docs/OPEN_API.md。
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_db
from backend.app.core.errors import ApiError
from backend.app.core.lan import detect_lan_ips
from backend.app.core.version import APP_VERSION
from backend.app.models.ai.model_config import AiDefaultBinding, AiModelProfile
from backend.app.models.ai.task import AiResult, AiTask
from backend.app.schemas.ai.open_api import (
    OpenDefaultModelInfo,
    OpenGeneratePayload,
    OpenInfoOut,
    OpenModelInfo,
    OpenResultOut,
    OpenTaskOut,
)
from backend.app.services.ai.generation_service import submit_image_generation
from backend.app.services.ai.storage_service import DEFAULT_AI_FOLDER_NAME, stage_upload_file

OPEN_PATH_PREFIX = "/api/v1/open"
TERMINAL_STATUSES = {"succeeded", "partial_failed", "failed", "canceled"}
CAPABILITY_KEYS = ("image_generate", "image_edit", "image_understand", "text_optimize")

router = APIRouter(prefix="/open", tags=["open-api"])


def _open_base_urls(request: Request) -> list[str]:
    port = request.url.port or (443 if request.url.scheme == "https" else 80)
    return [f"http://{ip}:{port}{OPEN_PATH_PREFIX}" for ip in detect_lan_ips()]


def _default_binding(db: Session, capability: str) -> AiDefaultBinding | None:
    bindings = (
        db.query(AiDefaultBinding)
        .filter(
            AiDefaultBinding.capability == capability,
            AiDefaultBinding.scene.in_(("global", "general")),
        )
        .all()
    )
    by_scene = {b.scene: b for b in bindings}
    return by_scene.get("global") or by_scene.get("general")


def _is_cap_supported(cap_val: Any) -> bool:
    if isinstance(cap_val, dict):
        return bool(cap_val.get("supported", False))
    return bool(cap_val)


@router.get("/info", response_model=OpenInfoOut)
def open_info(request: Request, db: Annotated[Session, Depends(get_db)]) -> OpenInfoOut:
    models_info: list[OpenModelInfo] = []
    profiles = db.query(AiModelProfile).filter(AiModelProfile.enabled.is_(True)).all()
    for p in profiles:
        caps = [key for key in CAPABILITY_KEYS if _is_cap_supported(p.capabilities.get(key))]
        if not caps:
            continue
        models_info.append(
            OpenModelInfo(
                id=p.id,
                name=p.name,
                model_id=p.model_id,
                provider_name=p.provider.name if p.provider else "",
                capabilities=caps,
            )
        )
    default_models = {}
    for capability in ("image_generate", "image_edit"):
        binding = _default_binding(db, capability)
        profile = binding.model_profile if binding else None
        default_models[capability] = OpenDefaultModelInfo(
            model_profile_id=profile.id if profile else None,
            name=profile.name if profile else None,
        )
    return OpenInfoOut(
        version=APP_VERSION,
        open_api_prefix=OPEN_PATH_PREFIX,
        open_base_urls=_open_base_urls(request),
        default_ai_folder=DEFAULT_AI_FOLDER_NAME,
        default_models=default_models,
        models=models_info,
    )


def _stage_open_references(db: Session, payload: OpenGeneratePayload) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for ref in payload.references:
        if ref.image_base64:
            b64_str = ref.image_base64
            if "," in b64_str and b64_str.strip().startswith("data:"):
                b64_str = b64_str.split(",", 1)[1]
            try:
                raw = base64.b64decode(b64_str)
            except Exception as exc:
                raise ApiError(code="invalid_base64", message=f"参考图 Base64 解析失败: {exc}", status_code=400)
            staged = stage_upload_file(db=db, file_content=raw, filename=ref.filename or "reference.png")
            refs.append({"source_kind": "local_upload", "source_id": staged["upload_id"], "role": ref.role})
        elif ref.asset_id is not None:
            refs.append({"source_kind": "asset", "source_id": str(ref.asset_id), "role": ref.role})
        else:
            refs.append({"source_kind": "history_result", "source_id": str(ref.history_result_id), "role": ref.role})
    return refs


def _build_params(payload: OpenGeneratePayload) -> dict[str, Any]:
    extra: dict[str, Any] = dict(payload.extra_params or {})
    if payload.negative_prompt:
        extra.setdefault("negative_prompt", payload.negative_prompt)
    if payload.seed is not None:
        extra.setdefault("seed", payload.seed)
    if payload.quality:
        extra.setdefault("quality", payload.quality)
    params: dict[str, Any] = {
        "n": payload.n,
        "timeout": float(payload.request_timeout_s),
        "extra_params": extra,
        "auto_import": payload.auto_import,
    }
    if payload.target_folder_id is not None:
        params["target_folder_id"] = payload.target_folder_id
    if payload.size:
        params["size"] = payload.size
    if payload.aspect_ratio:
        params["aspect_ratio"] = payload.aspect_ratio
    return params


def _task_out(db: Session, task: AiTask, request: Request | None = None) -> OpenTaskOut:
    results = (
        db.query(AiResult)
        .filter(AiResult.task_id == task.id, AiResult.is_deleted.is_(False))
        .order_by(AiResult.created_at, AiResult.idx)
        .all()
    )
    base_url = str(request.base_url).rstrip("/") if request else None
    return OpenTaskOut(
        task_id=task.id,
        task_type=task.task_type,
        status=task.status,
        progress_pct=task.progress_pct,
        prompt=task.prompt_final,
        model_profile_id=task.model_profile_id,
        error_code=task.error_code,
        error_message=task.error_message,
        created_at=task.created_at.isoformat(),
        results=[
            OpenResultOut(
                result_id=r.id,
                idx=r.idx,
                mime_type=r.mime_type,
                width=r.width,
                height=r.height,
                size_bytes=r.size_bytes,
                content_path=f"{OPEN_PATH_PREFIX}/images/results/{r.id}/content",
                content_url=f"{base_url}{OPEN_PATH_PREFIX}/images/results/{r.id}/content" if base_url else None,
                imported_asset_id=r.imported_asset_id,
            )
            for r in results
        ],
    )


async def _wait_task_out(request: Request, task_id: str, timeout_s: int) -> OpenTaskOut:
    session_factory = request.app.state.session_factory
    if session_factory is None:
        raise ApiError("db_unavailable", "本地数据库尚未初始化。", 500)
    waited = 0.0
    while True:
        with session_factory() as db:
            task = db.get(AiTask, task_id)
            if not task:
                raise ApiError(code="task_not_found", message=f"任务 {task_id} 不存在", status_code=404)
            out = _task_out(db, task, request=request)
        if out.status in TERMINAL_STATUSES or waited >= timeout_s:
            return out
        await asyncio.sleep(0.5)
        waited += 0.5


@router.post("/images/generations", response_model=OpenTaskOut, status_code=201)
async def open_generate_image(
    request: Request,
    payload: OpenGeneratePayload,
    db: Annotated[Session, Depends(get_db)],
):
    refs = _stage_open_references(db, payload)
    task_type = payload.task_type
    if task_type == "auto":
        task_type = "image_edit" if refs else "image_generate"

    task = submit_image_generation(
        db=db,
        prompt=payload.prompt,
        model_profile_id=payload.model_profile_id,
        params=_build_params(payload),
        references=refs,
        raw_user_request=payload.prompt,
        task_type=task_type,
    )
    if payload.wait:
        return await _wait_task_out(request, task.id, payload.wait_timeout_s)
    return _task_out(db, task, request=request)


@router.get("/images/tasks/{task_id}", response_model=OpenTaskOut)
def open_task_detail(
    task_id: str,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> OpenTaskOut:
    task = db.get(AiTask, task_id)
    if not task:
        raise ApiError(code="task_not_found", message=f"任务 {task_id} 不存在", status_code=404)
    return _task_out(db, task, request=request)


@router.get("/images/results/{result_id}/content")
@router.get("/open/images/results/{result_id}/content")
@router.get("/api/v1/open/images/results/{result_id}/content")
def open_result_content(result_id: str, db: Annotated[Session, Depends(get_db)]) -> FileResponse:
    result = db.get(AiResult, result_id)
    if not result or result.is_deleted:
        raise ApiError(code="result_not_found", message=f"生成结果 {result_id} 不存在或已删除", status_code=404)
    path = Path(result.history_file_path)
    if not path.exists():
        raise ApiError(code="file_not_found", message="结果实体文件在磁盘上丢失", status_code=404)
    return FileResponse(str(path), media_type=result.mime_type or "image/png")
