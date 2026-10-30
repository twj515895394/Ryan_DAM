from __future__ import annotations

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.errors import ApiError
from backend.app.models.ai.model_config import AiDefaultBinding, AiModelProfile
from backend.app.models.ai.provider import AiProviderInstance
from backend.app.models.ai.task import AiResult, AiTask, AiTaskReference
from backend.app.models.asset import Asset
from backend.app.services.ai.adapters.openai_compatible import OpenAICompatibleAdapter
from backend.app.services.ai.credentials import CredentialManager
from backend.app.services.ai.image_canvas import (
    adapt_reference_canvas_for_aspect_ratio,
    align_output_dimensions,
    parse_aspect_ratio,
)
from backend.app.services.ai.storage_service import (
    check_storage_space,
    commit_generated_result,
    get_ai_history_layout,
    import_result_to_asset,
    save_input_snapshot,
)
from backend.app.services.ai.task_scheduler import get_task_scheduler
from backend.app.services.settings_service import get_managed_root

logger = logging.getLogger(__name__)


def resolve_generation_model(
    db: Session,
    model_profile_id: int | None = None,
    capability: str = "image_generate",
) -> AiModelProfile:
    """解析用于文生图/图像编辑的模型配置：优先使用手动指定，其次使用默认绑定。"""
    if model_profile_id:
        profile = db.query(AiModelProfile).filter(AiModelProfile.id == model_profile_id).first()
        if not profile:
            raise ApiError(code="model_not_found", message=f"指定的模型配置 #{model_profile_id} 不存在", status_code=404)
        if not profile.enabled:
            raise ApiError(code="model_disabled", message=f"模型 {profile.name} 已被禁用", status_code=400)
        return profile

    # 查询默认绑定 capability：设置界面写入的绑定 scene 为 "global"，
    # 历史数据可能存在 "general" 脏值，两者兼容且以 "global" 优先。
    bindings = (
        db.query(AiDefaultBinding)
        .filter(
            AiDefaultBinding.capability == capability,
            AiDefaultBinding.scene.in_(("global", "general")),
        )
        .all()
    )
    by_scene = {b.scene: b for b in bindings}
    binding = by_scene.get("global") or by_scene.get("general")
    if binding and binding.model_profile and binding.model_profile.enabled:
        return binding.model_profile

    # 回退到任一启用了对应能力或兼容能力（如 image_generate）的模型
    all_models = db.query(AiModelProfile).filter(AiModelProfile.enabled.is_(True)).all()
    for m in all_models:
        if m.capabilities and m.capabilities.get(capability):
            return m
        if capability == "image_edit" and m.capabilities and m.capabilities.get("image_generate"):
            return m

    raise ApiError(
        code="no_model_available",
        message=f"未指定模型，且系统尚未配置 {capability} 可用模型，请在设置中配置可用模型",
        status_code=400,
    )


def submit_image_generation(
    db: Session,
    prompt: str,
    model_profile_id: int | None = None,
    preset_id: int | None = None,
    params: dict[str, Any] | None = None,
    reference_asset_ids: list[int] | None = None,
    references: list[Any] | None = None,
    raw_user_request: str | None = None,
    task_type: str = "image_generate",
    retry_of: str | None = None,
) -> AiTask:
    """提交文生图或图像编辑任务至异步调度器。"""
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise ApiError(code="empty_prompt", message="生成提示词不能为空", status_code=422)

    if task_type == "image_edit" and not references and not reference_asset_ids:
        raise ApiError(code="missing_reference", message="图像编辑任务必须提供至少一张参考图像", status_code=422)

    model_profile = resolve_generation_model(db, model_profile_id, capability=task_type)
    provider = model_profile.provider
    if not provider or not provider.enabled:
        raise ApiError(code="provider_disabled", message="所选模型所属的 Provider 处于未启用状态", status_code=400)

    # 预检存储空间
    managed_root = get_managed_root(db)
    check_storage_space(managed_root)

    scheduler = get_task_scheduler()
    task = scheduler.create_task(
        db=db,
        task_type=task_type,
        provider_id=provider.id,
        model_profile_id=model_profile.id,
        preset_id=preset_id,
        prompt_final=cleaned_prompt,
        raw_user_request=raw_user_request,
        params=params or {},
        retry_of=retry_of,
    )

    # 如果有参考图输入，规范化多源参考项并保存不可变快照
    ref_list: list[dict[str, Any]] = []
    if references:
        for r in references:
            if hasattr(r, "model_dump"):
                ref_list.append(r.model_dump())
            elif isinstance(r, dict):
                ref_list.append(r)
    if reference_asset_ids:
        for aid in reference_asset_ids:
            if not any(item.get("source_kind") == "asset" and str(item.get("source_id")) == str(aid) for item in ref_list):
                ref_list.append({"source_kind": "asset", "source_id": str(aid), "role": "reference"})

    layout = get_ai_history_layout(managed_root)
    for seq, item in enumerate(ref_list):
        source_kind = item.get("source_kind")
        source_id = str(item.get("source_id"))
        role = item.get("role") or "reference"
        source_p: Path | None = None

        if source_kind == "asset":
            asset = db.get(Asset, int(source_id)) if source_id.isdigit() else None
            if asset and asset.file_path:
                source_p = Path(asset.file_path)
        elif source_kind == "history_result":
            from backend.app.models.ai.task import AiResult
            res = db.get(AiResult, source_id)
            if res and res.history_file_path:
                source_p = Path(res.history_file_path)
        elif source_kind == "local_upload":
            p = layout["staging"] / source_id
            if p.exists() and p.is_file():
                source_p = p

        if source_p and source_p.exists() and source_p.is_file():
            save_input_snapshot(
                db=db,
                task_id=task.id,
                seq=seq,
                source_path=source_p,
                role=role,
                source_kind=source_kind or "asset",
                source_id=source_id,
            )

    # 分发至调度器异步执行
    scheduler.dispatch(task.id, _make_generation_runner(scheduler.session_factory))
    return task


def auto_import_task_results(
    session_factory: sessionmaker,
    task_id: str,
    target_folder_id: int | None = None,
) -> list[dict[str, Any]]:
    """把任务的全部成功生成结果自动入库为托管资产（开放接口 auto_import 语义）。

    target_folder_id 为空时由存储层兜底落『AI 生成』默认目录。单条失败只记日志，
    不影响其余结果——生成历史已永久落盘，用户仍可在工作台手动补入库。
    """
    imported: list[dict[str, Any]] = []
    with session_factory() as db:
        results = (
            db.query(AiResult)
            .filter(AiResult.task_id == task_id, AiResult.is_deleted.is_(False))
            .order_by(AiResult.created_at, AiResult.idx)
            .all()
        )
        for res in results:
            try:
                asset, _is_new = import_result_to_asset(db, res.id, target_folder_id=target_folder_id)
                imported.append({"result_id": res.id, "asset_id": asset.id})
            except Exception as exc:
                logger.warning(f"auto_import 结果 {res.id}（任务 {task_id}）入库失败: {exc}")
                db.rollback()
    return imported


def _make_generation_runner(session_factory: sessionmaker):
    async def _runner(task_id: str, cancel_event: asyncio.Event) -> None:
        scheduler = get_task_scheduler()
        with session_factory() as db:
            task = db.query(AiTask).filter(AiTask.id == task_id).first()
            if not task:
                return
            task_type = task.task_type
            provider = task.provider
            model_profile = task.model_profile
            prompt = task.prompt_final or ""
            params = task.params
            managed_root = get_managed_root(db)

            primary_image_path: Path | None = None
            mask_image_path: Path | None = None
            if task_type == "image_edit":
                ref_records = (
                    db.query(AiTaskReference)
                    .filter(AiTaskReference.task_id == task_id)
                    .order_by(AiTaskReference.seq)
                    .all()
                )
                for r in ref_records:
                    if r.role == "mask" and not mask_image_path:
                        mask_image_path = Path(r.snapshot_path)
                    elif not primary_image_path:
                        primary_image_path = Path(r.snapshot_path)

            if not provider or not model_profile:
                scheduler.update_task_status(
                    task_id, "failed", error_code="config_missing", error_message="Provider 或模型配置已丢失"
                )
                return

            api_key = CredentialManager.get_credential(provider.credential_ref)
            if not api_key:
                scheduler.update_task_status(
                    task_id, "failed", error_code="api_key_missing", error_message="未配置该连接的 API Key"
                )
                return

        # 准备暂存目录
        layout = get_ai_history_layout(managed_root)
        staging_dir = layout["staging"] / task_id
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            if cancel_event.is_set():
                scheduler.update_task_status(task_id, "canceled")
                return

            provider_settings = json.loads(provider.settings_json) if provider.settings_json else {}
            adapter = OpenAICompatibleAdapter(
                base_url=provider.base_url,
                api_key=api_key,
                model_id=model_profile.model_id,
                settings=provider_settings,
            )

            # 提取生图参数
            n = int(params.get("n", 1))
            size = str(params.get("size", "1024x1024"))
            timeout = float(params.get("timeout", 120.0))

            scheduler.update_task_status(task_id, "running", progress_pct=10)

            if task_type == "image_edit":
                if not primary_image_path or not primary_image_path.exists():
                    raise ApiError(code="missing_reference_file", message="未找到用于编辑的参考图快照文件", status_code=404)
                img_bytes_in = primary_image_path.read_bytes()
                mask_bytes_in = mask_image_path.read_bytes() if mask_image_path and mask_image_path.exists() else None

                # 自适应目标画幅比例（防止上游编辑接口因参考图原始比例固化输出画幅）
                target_ratio = parse_aspect_ratio(
                    aspect_ratio_str=params.get("aspect_ratio"),
                    size_str=size,
                )
                if target_ratio:
                    img_bytes_in, mask_bytes_in = adapt_reference_canvas_for_aspect_ratio(
                        image_bytes=img_bytes_in,
                        mask_bytes=mask_bytes_in,
                        target_ratio=target_ratio,
                    )

                image_bytes_list = await adapter.edit_image(
                    image_bytes=img_bytes_in,
                    prompt=prompt,
                    mask_bytes=mask_bytes_in,
                    n=n,
                    size=size,
                    adapter_kind=model_profile.adapter_kind,
                    extra_params=params.get("extra_params"),
                    timeout=timeout,
                )
            else:
                image_bytes_list = await adapter.generate_images(
                    prompt=prompt,
                    n=n,
                    size=size,
                    adapter_kind=model_profile.adapter_kind,
                    extra_params=params.get("extra_params"),
                    timeout=timeout,
                )

            if cancel_event.is_set():
                scheduler.update_task_status(task_id, "canceled")
                return

            # 对输出图像进行尺寸规格对齐（例如 1672x941 与 1920x1080 相同比例下的精细对齐）
            aligned_bytes_list: list[bytes] = []
            for raw_bytes in image_bytes_list:
                aligned = align_output_dimensions(raw_bytes, target_size_str=size)
                aligned_bytes_list.append(aligned)
            image_bytes_list = aligned_bytes_list

            # 落盘并记录生成结果
            with session_factory() as db:
                for idx, img_bytes in enumerate(image_bytes_list):
                    staging_file = staging_dir / f"{idx}.png"
                    staging_file.write_bytes(img_bytes)
                    commit_generated_result(
                        db=db,
                        task_id=task_id,
                        idx=idx,
                        staging_file=staging_file,
                        mime_type="image/png",
                    )

            scheduler.update_task_status(task_id, "succeeded", progress_pct=100)

            # 外部开放接口的自动入库语义：成功后把结果导入目标目录（缺省「AI 生成」）
            if params.get("auto_import"):
                auto_import_task_results(
                    session_factory,
                    task_id,
                    target_folder_id=params.get("target_folder_id"),
                )

        except asyncio.CancelledError:
            logger.info(f"Task {task_id} canceled during execution")
            scheduler.update_task_status(task_id, "canceled")
        except ApiError as api_err:
            logger.warning(f"Task {task_id} failed with ApiError: {api_err.message}")
            scheduler.update_task_status(
                task_id, "failed", error_code=api_err.code, error_message=api_err.message
            )
        except Exception as exc:
            logger.exception(f"Task {task_id} failed with unexpected error: {exc}")
            scheduler.update_task_status(
                task_id, "failed", error_code="execution_failed", error_message=str(exc)
            )
        finally:
            # 清理 staging 目录，确保不留悬空半成品
            if staging_dir.exists():
                try:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                except Exception as clean_err:
                    logger.warning(f"Failed to cleanup staging dir: {clean_err}")

    return _runner
