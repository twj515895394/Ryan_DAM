from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.errors import ApiError
from backend.app.db.base import utcnow
from backend.app.models.ai.provider import AiProviderInstance
from backend.app.models.ai.model_config import AiModelProfile
from backend.app.models.ai.template import AiReverseTemplate
from backend.app.models.ai.task import AiTask, AiTaskItem
from backend.app.models.asset import Asset
from backend.app.schemas.ai.template import (
    ReverseTemplateCreate,
    ReverseTemplateUpdate,
    SingleImageReverseRequest,
    SingleImageReverseResult,
)
from backend.app.services.ai.model_service import resolve_model_for_capability
from backend.app.services.ai.credentials import CredentialManager
from backend.app.services.ai.adapters.openai_compatible import OpenAICompatibleAdapter
from backend.app.services.ai.task_scheduler import get_task_scheduler

logger = logging.getLogger(__name__)

BUILTIN_TEMPLATES = [
    {
        "name": "通用画面描述",
        "code": "general_description",
        "description": "全面客观地解析画面主体、构图、光影、材质与色彩细节",
        "system_prompt": (
            "你是一个专业的视觉分析与反推助手。请忠实、细致地客观描述输入图片中可观察到的一切视觉事实，"
            "包含主体对象、动作与姿态、环境场景、构图透视、光影氛围、材质细节与色彩基调。"
            "禁止假定或虚构拍摄相机、镜头型号、作者真实心智或原作者 Prompt，仅对画面客观真实呈现做出英文提示词风格的详细描述。"
        ),
        "user_prompt_template": "请以 Stable Diffusion / Midjourney 风格的高质量提示词结构输出上述画面的客观视觉描述：",
        "sort_order": 1,
    },
    {
        "name": "人物与角色特征",
        "code": "character_features",
        "description": "侧重主体人物的五官、发型发色、体貌特征、服装穿搭与姿态微表情",
        "system_prompt": (
            "你是一个角色设计与视觉特征解析专家。请深入解析画面中人物角色的外貌细节，包括："
            "年龄段、性别、发型与发色、面部特征、神态表情、身形体态、服饰搭配（材质、版型、颜色、图案及配饰细节）。"
            "严格基于画面客观细节进行描述，避免臆测人物身份或故事背景。"
        ),
        "user_prompt_template": "请重点针对人物/角色外观与衣着特征，输出精准生动的提示词描述：",
        "sort_order": 2,
    },
    {
        "name": "艺术与摄影风格",
        "code": "artistic_style",
        "description": "侧重画风流派、媒介类型（胶片/数码/3D渲染/手绘插画）、色彩配比与光影质感",
        "system_prompt": (
            "你是一个艺术史与摄影美学分析师。请解析画面的视觉艺术风格、媒介类型（如油画、水彩、3D 数字渲染、胶片摄影、数码摄影等）、"
            "色彩调色板（主色调、对比色、饱和度）、光影表现（单侧光、逆光、柔光、丁达尔效应等）与镜头景深质感。"
            "以专业美学术语提炼出风格标签与核心 Prompt 词汇。"
        ),
        "user_prompt_template": "请针对画面的艺术媒介、色彩与摄影构图风格提炼精准提示词：",
        "sort_order": 3,
    },
]


def ensure_builtin_templates(db: Session) -> None:
    """确保内置反推模板初始化进数据库。"""
    for tpl_data in BUILTIN_TEMPLATES:
        existing = db.query(AiReverseTemplate).filter(AiReverseTemplate.code == tpl_data["code"]).first()
        if not existing:
            new_tpl = AiReverseTemplate(
                name=tpl_data["name"],
                code=tpl_data["code"],
                description=tpl_data["description"],
                system_prompt=tpl_data["system_prompt"],
                user_prompt_template=tpl_data["user_prompt_template"],
                is_builtin=True,
                enabled=True,
                sort_order=tpl_data["sort_order"],
            )
            db.add(new_tpl)
    db.commit()


def list_reverse_templates(db: Session, enabled_only: bool = False) -> list[AiReverseTemplate]:
    ensure_builtin_templates(db)
    query = db.query(AiReverseTemplate)
    if enabled_only:
        query = query.filter(AiReverseTemplate.enabled.is_(True))
    return query.order_by(AiReverseTemplate.sort_order.asc(), AiReverseTemplate.id.asc()).all()


def get_reverse_template(db: Session, template_id: int) -> AiReverseTemplate:
    tpl = db.query(AiReverseTemplate).filter(AiReverseTemplate.id == template_id).first()
    if not tpl:
        raise ApiError(code="template_not_found", message=f"反推模板 #{template_id} 不存在", status_code=404)
    return tpl


def create_reverse_template(db: Session, payload: ReverseTemplateCreate) -> AiReverseTemplate:
    tpl = AiReverseTemplate(
        name=payload.name,
        code=payload.code,
        description=payload.description,
        system_prompt=payload.system_prompt,
        user_prompt_template=payload.user_prompt_template,
        default_model_profile_id=payload.default_model_profile_id,
        is_builtin=False,
        enabled=payload.enabled,
        sort_order=payload.sort_order,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


def update_reverse_template(db: Session, template_id: int, payload: ReverseTemplateUpdate) -> AiReverseTemplate:
    tpl = get_reverse_template(db, template_id)
    if payload.name is not None:
        tpl.name = payload.name
    if payload.description is not None:
        tpl.description = payload.description
    if payload.system_prompt is not None:
        tpl.system_prompt = payload.system_prompt
    if payload.user_prompt_template is not None:
        tpl.user_prompt_template = payload.user_prompt_template
    if payload.default_model_profile_id is not None:
        tpl.default_model_profile_id = payload.default_model_profile_id
    if payload.enabled is not None:
        tpl.enabled = payload.enabled
    if payload.sort_order is not None:
        tpl.sort_order = payload.sort_order
    db.commit()
    db.refresh(tpl)
    return tpl


def delete_reverse_template(db: Session, template_id: int) -> None:
    tpl = get_reverse_template(db, template_id)
    if tpl.is_builtin:
        raise ApiError(code="cannot_delete_builtin", message="系统内置反推模板不可删除", status_code=400)
    db.delete(tpl)
    db.commit()


async def reverse_single_image(
    db: Session, asset_id: int, request: SingleImageReverseRequest
) -> SingleImageReverseResult:
    """对单张图片资产执行视觉反推。"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise ApiError(code="asset_not_found", message=f"资产 #{asset_id} 不存在", status_code=404)

    if asset.asset_type != "image":
        raise ApiError(code="invalid_asset_type", message="只有图片资产支持视觉提示词反推", status_code=400)

    file_path = Path(asset.file_path)
    if not file_path.exists():
        raise ApiError(code="file_not_found", message=f"图片源文件不存在：{asset.file_path}", status_code=404)

    # 1. 确定模板与 Prompt
    template_name = "默认反推"
    system_prompt = request.custom_system_prompt
    user_instruction = request.user_instruction

    if request.template_id:
        tpl = get_reverse_template(db, request.template_id)
        template_name = tpl.name
        if not system_prompt:
            system_prompt = tpl.system_prompt
        if not user_instruction:
            user_instruction = tpl.user_prompt_template or "请输出该图片的详细视觉提示词："

    if not system_prompt:
        ensure_builtin_templates(db)
        default_tpl = db.query(AiReverseTemplate).filter(AiReverseTemplate.code == "general_description").first()
        if default_tpl:
            template_name = default_tpl.name
            system_prompt = default_tpl.system_prompt
            user_instruction = user_instruction or default_tpl.user_prompt_template
        else:
            system_prompt = "请客观描述图片中的所有视觉细节要素与构图质感。"

    if not user_instruction:
        user_instruction = "请输出该图片的详细视觉提示词："

    # 2. 路由视觉模型 (image_understand)
    model_profile, provider = resolve_model_for_capability(
        db,
        capability="image_understand",
        manual_profile_id=request.model_profile_id,
        scene="reverse_prompt",
    )

    # 3. 读取凭据
    api_key = CredentialManager.get_credential(provider.credential_ref) if provider.credential_ref else ""

    # 4. 读取图片并编码为 base64
    image_bytes = file_path.read_bytes()
    mime = "image/jpeg"
    ext = file_path.suffix.lower()
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    image_base64 = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"

    # 5. 调用适配器
    settings_dict = json.loads(provider.settings_json) if provider.settings_json else {}
    adapter = OpenAICompatibleAdapter(
        base_url=provider.base_url,
        api_key=api_key,
        model_id=model_profile.model_id,
        settings=settings_dict,
    )

    reversed_prompt = await adapter.understand_image(
        image_base64_or_url=image_base64,
        prompt=user_instruction,
        system_prompt=system_prompt,
    )

    return SingleImageReverseResult(
        asset_id=asset.id,
        reversed_prompt=reversed_prompt,
        template_name=template_name,
        model_id=model_profile.model_id,
        model_name=model_profile.name,
        provider_name=provider.name,
        has_conflict=bool(asset.prompt_text),
        current_asset_prompt=asset.prompt_text,
        current_asset_revision=asset.prompt_revision or 1,
    )


def submit_batch_reverse(
    db: Session,
    asset_ids: list[int],
    template_id: int | None = None,
    model_profile_id: int | None = None,
    custom_system_prompt: str | None = None,
    user_instruction: str | None = None,
) -> AiTask:
    """提交批量图片提示词反推任务至异步受控并发调度器。"""
    if not asset_ids:
        raise ApiError(code="empty_asset_ids", message="请至少选择一张图片资产进行批量反推", status_code=422)

    assets = db.query(Asset).filter(Asset.id.in_(asset_ids), Asset.status == "active").all()
    image_assets = [a for a in assets if a.asset_type == "image"]
    if not image_assets:
        raise ApiError(code="no_valid_images", message="所选资产中没有可用于反推的图片资产", status_code=422)

    # 确定反推模板与 Prompt 指令
    system_prompt = custom_system_prompt
    user_prompt = user_instruction
    template_name = "默认反推"
    if template_id:
        tpl = get_reverse_template(db, template_id)
        template_name = tpl.name
        if not system_prompt:
            system_prompt = tpl.system_prompt
        if not user_prompt:
            user_prompt = tpl.user_prompt_template or "请输出该图片的详细视觉提示词："
    else:
        ensure_builtin_templates(db)
        default_tpl = db.query(AiReverseTemplate).filter(AiReverseTemplate.code == "general_description").first()
        if default_tpl:
            template_name = default_tpl.name
            system_prompt = system_prompt or default_tpl.system_prompt
            user_prompt = user_prompt or default_tpl.user_prompt_template

    system_prompt = system_prompt or "请客观描述图片中的所有视觉细节要素与构图质感。"
    user_prompt = user_prompt or "请输出该图片的详细视觉提示词："

    # 路由视觉模型 (image_understand)
    model_profile, provider = resolve_model_for_capability(
        db,
        capability="image_understand",
        manual_profile_id=model_profile_id,
        scene="reverse_prompt",
    )

    scheduler = get_task_scheduler()
    task = scheduler.create_task(
        db=db,
        task_type="batch_reverse",
        provider_id=provider.id,
        model_profile_id=model_profile.id,
        preset_id=None,
        prompt_final=f"批量反推 {len(image_assets)} 张图片（{template_name}）",
        raw_user_request=user_prompt,
        params={
            "template_id": template_id,
            "template_name": template_name,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        },
    )

    for a in image_assets:
        item = AiTaskItem(
            task_id=task.id,
            asset_id=a.id,
            status="pending",
            prompt_revision_at_start=a.prompt_revision or 1,
        )
        db.add(item)
    db.commit()

    scheduler.dispatch(task.id, _make_batch_reverse_runner(scheduler.session_factory))
    return task


def _make_batch_reverse_runner(session_factory: sessionmaker):
    async def _runner(task_id: str, cancel_event: asyncio.Event) -> None:
        scheduler = get_task_scheduler()
        with session_factory() as db:
            task = db.query(AiTask).filter(AiTask.id == task_id).first()
            if not task:
                return
            provider = task.provider
            model_profile = task.model_profile
            params = task.params
            system_prompt = params.get("system_prompt") or "请客观描述图片中的所有视觉细节要素与构图质感。"
            user_prompt = params.get("user_prompt") or "请输出该图片的详细视觉提示词："

            if not provider or not model_profile:
                scheduler.update_task_status(
                    task_id, "failed", error_code="config_missing", error_message="Provider 或模型配置已丢失"
                )
                return

            api_key = CredentialManager.get_credential(provider.credential_ref) if provider.credential_ref else ""
            provider_settings = json.loads(provider.settings_json) if provider.settings_json else {}

            item_records = (
                db.query(AiTaskItem)
                .filter(AiTaskItem.task_id == task_id)
                .order_by(AiTaskItem.id)
                .all()
            )
            items_to_process = [(it.id, it.asset_id) for it in item_records]

        adapter = OpenAICompatibleAdapter(
            base_url=provider.base_url,
            api_key=api_key,
            model_id=model_profile.model_id,
            settings=provider_settings,
        )

        total = len(items_to_process)
        completed = 0
        succeeded_count = 0

        sem = asyncio.Semaphore(3)

        async def _process_item(item_id: int, asset_id: int | None) -> None:
            nonlocal completed, succeeded_count
            if cancel_event.is_set():
                with session_factory() as db:
                    it = db.get(AiTaskItem, item_id)
                    if it and it.status == "pending":
                        it.status = "skipped"
                        db.commit()
                return

            async with sem:
                if cancel_event.is_set():
                    return

                with session_factory() as db:
                    it = db.get(AiTaskItem, item_id)
                    if it:
                        it.status = "running"
                        db.commit()
                    asset = db.get(Asset, asset_id) if asset_id else None
                    if not asset or not asset.file_path:
                        if it:
                            it.status = "failed"
                            it.error_code = "file_not_found"
                            it.error_message = "资产文件不存在"
                            db.commit()
                        completed += 1
                        return
                    p = Path(asset.file_path)
                    if not p.exists() or not p.is_file():
                        if it:
                            it.status = "failed"
                            it.error_code = "file_not_found"
                            it.error_message = f"文件路径不存在: {asset.file_path}"
                            db.commit()
                        completed += 1
                        return
                    file_path = p

                try:
                    ext = file_path.suffix.lower()
                    mime = "image/png" if ext == ".png" else "image/webp" if ext == ".webp" else "image/jpeg"
                    img_bytes = file_path.read_bytes()
                    b64_str = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"

                    reversed_text = await adapter.understand_image(
                        image_base64_or_url=b64_str,
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                    )

                    with session_factory() as db:
                        it = db.get(AiTaskItem, item_id)
                        if it:
                            it.status = "succeeded"
                            it.draft_prompt_text = reversed_text
                            db.commit()
                    succeeded_count += 1
                except Exception as exc:
                    logger.warning("反推单图失败 item_id=%s: %s", item_id, exc)
                    with session_factory() as db:
                        it = db.get(AiTaskItem, item_id)
                        if it:
                            it.status = "failed"
                            it.error_code = "reverse_error"
                            it.error_message = str(exc)
                            db.commit()
                finally:
                    completed += 1
                    pct = int((completed / total) * 100) if total > 0 else 100
                    with session_factory() as db:
                        t = db.query(AiTask).filter(AiTask.id == task_id).first()
                        if t and t.status == "running":
                            t.progress_pct = pct
                            db.commit()

        tasks = [_process_item(item_id, asset_id) for item_id, asset_id in items_to_process]
        await asyncio.gather(*tasks, return_exceptions=True)

        with session_factory() as db:
            task = db.query(AiTask).filter(AiTask.id == task_id).first()
            if not task:
                return
            if cancel_event.is_set():
                task.status = "canceled"
            elif succeeded_count == total:
                task.status = "succeeded"
            elif succeeded_count > 0:
                task.status = "partial_failed"
            else:
                task.status = "failed"
                task.error_message = "所有图片反推均失败"
            task.finished_at = utcnow()
            task.progress_pct = 100
            db.commit()

    return _runner


def commit_batch_reverse_items(
    db: Session,
    task_id: str,
    item_ids: list[int],
    edited_drafts: dict[int, str] | None = None,
    allow_overwrite: bool = False,
) -> dict[str, Any]:
    """批量审核并采纳反推提示词至资产库（具备 CAS 保护与防静默覆盖保护）。"""
    task = db.query(AiTask).filter(AiTask.id == task_id).first()
    if not task:
        raise ApiError(code="task_not_found", message=f"任务 #{task_id} 不存在", status_code=404)

    items = db.query(AiTaskItem).filter(AiTaskItem.task_id == task_id, AiTaskItem.id.in_(item_ids)).all()
    committed_count = 0
    skipped_count = 0
    conflict_count = 0
    details: list[dict[str, Any]] = []

    for item in items:
        if item.status != "succeeded":
            skipped_count += 1
            details.append({"item_id": item.id, "status": "skipped", "reason": f"当前状态不可提交（{item.status}）"})
            continue

        asset = db.get(Asset, item.asset_id) if item.asset_id else None
        if not asset:
            skipped_count += 1
            details.append({"item_id": item.id, "status": "skipped", "reason": "对应资产不存在"})
            continue

        draft_to_save = (edited_drafts.get(item.id) if edited_drafts and item.id in edited_drafts else item.draft_prompt_text) or ""
        if not draft_to_save.strip():
            skipped_count += 1
            details.append({"item_id": item.id, "status": "skipped", "reason": "反推草稿内容为空"})
            continue

        has_existing_prompt = bool(asset.prompt_text and asset.prompt_text.strip())
        prompt_modified_since_start = (asset.prompt_revision or 1) != (item.prompt_revision_at_start or 1)

        if has_existing_prompt and not allow_overwrite:
            conflict_count += 1
            details.append({
                "item_id": item.id,
                "asset_id": asset.id,
                "status": "conflict",
                "reason": "资产已有提示词，未允许覆盖",
                "current_prompt": asset.prompt_text,
            })
            continue

        if prompt_modified_since_start and not allow_overwrite:
            conflict_count += 1
            details.append({
                "item_id": item.id,
                "asset_id": asset.id,
                "status": "conflict",
                "reason": "反推期间资产提示词发生过并发变更",
                "current_prompt": asset.prompt_text,
            })
            continue

        asset.prompt_text = draft_to_save
        asset.prompt_origin = "ai_reverse"
        asset.prompt_revision = (asset.prompt_revision or 1) + 1
        item.status = "committed"
        committed_count += 1
        details.append({
            "item_id": item.id,
            "asset_id": asset.id,
            "status": "committed",
            "new_revision": asset.prompt_revision,
        })

    db.commit()
    return {
        "committed_count": committed_count,
        "skipped_count": skipped_count,
        "conflict_count": conflict_count,
        "details": details,
    }

