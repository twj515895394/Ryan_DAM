from __future__ import annotations

import json
import logging
from typing import Any
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.ai.template import AiCreationPreset
from backend.app.schemas.ai.template import (
    CreationPresetCreate,
    CreationPresetUpdate,
    PromptOptimizeRequest,
    PromptOptimizeResult,
)
from backend.app.services.ai.adapters.openai_compatible import OpenAICompatibleAdapter
from backend.app.services.ai.credentials import CredentialManager
from backend.app.services.ai.model_service import resolve_model_for_capability

logger = logging.getLogger(__name__)

BUILTIN_CREATION_PRESETS = [
    {
        "code": "photorealistic",
        "name": "写实摄影 (Photorealistic)",
        "description": "极具细节质感的单反大片风格，模拟 8k 分辨率与逼真光学镜头光影",
        "creation_mode": "image_generate",
        "system_rules": "强调超逼真写实摄影质感、8k 分辨率、自然写实光影、Fujifilm 35mm f/1.8 镜头、层次丰富、皮肤与材质细节精细。坚决避免动漫化、3D 渲染感或塑料感虚假质感。",
        "default_params": {
            "prompt_suffix": ", 8k resolution, raw photo, realistic natural lighting, fine texture, sharp focus, 35mm lens, masterpiece",
            "negative_prompt": "cartoon, anime, 3d render, plastic, oversaturated, blurry, bad anatomy, deformed fingers, low quality",
        },
        "sort_order": 1,
    },
    {
        "code": "anime_art",
        "name": "二次元动漫 (Anime & Manga)",
        "description": "唯美精致的日系二次元插画风格，色彩通透，光斑梦幻",
        "creation_mode": "image_generate",
        "system_rules": "强调日本经典高质量动漫与手绘插画风格、清透丰富的色彩饱和度、精致干净的人物线稿、唯美漫反射与动态丁达尔光斑、动漫电影级唯美构图。",
        "default_params": {
            "prompt_suffix": ", masterpiece, high quality anime aesthetic, vibrant colors, delicate clean lineart, cinematic lighting, Makoto Shinkai style",
            "negative_prompt": "photorealistic, 3d, realistic human, western comic, muddy colors, lowres, bad hands",
        },
        "sort_order": 2,
    },
    {
        "code": "cyberpunk_neon",
        "name": "赛博朋克 (Cyberpunk Neon)",
        "description": "未来科技与霓虹暗调的强对比视觉，机械质感与雨夜反光",
        "creation_mode": "image_generate",
        "system_rules": "强调未来赛博朋克都市、深邃暗夜与绚烂霓虹灯光对撞、湿润路面雨水倒影、机械义体细节、高对比度与电影级冷暖色调对撞氛围。",
        "default_params": {
            "prompt_suffix": ", cyberpunk aesthetic, neon glow, wet rainy streets, futuristic reflections, mechanical details, cinematic night atmosphere",
            "negative_prompt": "pastoral, bright daylight, vintage, rustic, dull lighting, low contrast",
        },
        "sort_order": 3,
    },
    {
        "code": "commercial_product",
        "name": "商业静物 (Commercial Product)",
        "description": "高品质商业影棚产品打光，纯净极简背景，高级质感",
        "creation_mode": "image_generate",
        "system_rules": "强调商业产品摄影棚专业打光、柔光箱微漫反射、干净极简的优雅背景、产品边缘锐利纯净、高级奢华构图与材质反光表现。",
        "default_params": {
            "prompt_suffix": ", studio product photography, clean minimalist background, softbox lighting, high-end commercial shot, crisp edge, elegant composition",
            "negative_prompt": "cluttered background, noisy, harsh shadows, messy, low quality, distortion",
        },
        "sort_order": 4,
    },
]


def ensure_builtin_presets(db: Session) -> None:
    """初始化数据库中内置的 AI 创作预设。"""
    for item in BUILTIN_CREATION_PRESETS:
        existing = db.query(AiCreationPreset).filter(AiCreationPreset.code == item["code"]).first()
        if not existing:
            preset = AiCreationPreset(
                code=item["code"],
                name=item["name"],
                description=item["description"],
                creation_mode=item["creation_mode"],
                system_rules=item["system_rules"],
                default_params_json=json.dumps(item["default_params"], ensure_ascii=False),
                is_builtin=True,
                enabled=True,
                sort_order=item["sort_order"],
            )
            db.add(preset)
    db.commit()


def list_creation_presets(
    db: Session,
    creation_mode: str | None = None,
    enabled_only: bool = False,
) -> list[AiCreationPreset]:
    """获取创作预设列表。"""
    ensure_builtin_presets(db)
    query = db.query(AiCreationPreset)
    if creation_mode:
        query = query.filter(AiCreationPreset.creation_mode == creation_mode)
    if enabled_only:
        query = query.filter(AiCreationPreset.enabled.is_(True))
    return query.order_by(AiCreationPreset.sort_order.asc(), AiCreationPreset.id.asc()).all()


def get_creation_preset(db: Session, preset_id: int) -> AiCreationPreset:
    """获取单个创作预设。"""
    preset = db.query(AiCreationPreset).filter(AiCreationPreset.id == preset_id).first()
    if not preset:
        raise ApiError(code="preset_not_found", message=f"创作预设 #{preset_id} 不存在", status_code=404)
    return preset


def create_creation_preset(db: Session, payload: CreationPresetCreate) -> AiCreationPreset:
    """创建自定义创作预设。"""
    preset = AiCreationPreset(
        name=payload.name,
        code=payload.code,
        description=payload.description,
        creation_mode=payload.creation_mode,
        system_rules=payload.system_rules,
        default_model_profile_id=payload.default_model_profile_id,
        default_params_json=json.dumps(payload.default_params or {}, ensure_ascii=False),
        is_builtin=False,
        enabled=payload.enabled,
        sort_order=payload.sort_order,
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


def update_creation_preset(db: Session, preset_id: int, payload: CreationPresetUpdate) -> AiCreationPreset:
    """更新创作预设。"""
    preset = get_creation_preset(db, preset_id)
    if payload.name is not None:
        preset.name = payload.name
    if payload.description is not None:
        preset.description = payload.description
    if payload.system_rules is not None:
        preset.system_rules = payload.system_rules
    if payload.default_model_profile_id is not None:
        preset.default_model_profile_id = payload.default_model_profile_id
    if payload.default_params is not None:
        preset.default_params_json = json.dumps(payload.default_params, ensure_ascii=False)
    if payload.enabled is not None:
        preset.enabled = payload.enabled
    if payload.sort_order is not None:
        preset.sort_order = payload.sort_order

    db.commit()
    db.refresh(preset)
    return preset


def delete_creation_preset(db: Session, preset_id: int) -> None:
    """删除自定义创作预设（系统内置预设不允许删除）。"""
    preset = get_creation_preset(db, preset_id)
    if preset.is_builtin:
        raise ApiError(code="cannot_delete_builtin", message="系统内置创作预设不可删除", status_code=400)
    db.delete(preset)
    db.commit()


async def optimize_prompt(
    db: Session,
    request: PromptOptimizeRequest,
) -> PromptOptimizeResult:
    """调用 LLM (text_chat) 对用户原始提示词进行结构化扩写与润色。"""
    raw_prompt = request.prompt.strip()
    if not raw_prompt:
        raise ApiError(code="empty_prompt", message="待润色的提示词不能为空", status_code=400)

    # 1. 查找预设（如果有）
    preset: AiCreationPreset | None = None
    if request.preset_id:
        preset = db.get(AiCreationPreset, request.preset_id)
        if not preset or not preset.enabled:
            raise ApiError(code="preset_not_found", message=f"指定的创作预设 #{request.preset_id} 不存在或已停用", status_code=404)

    # 2. 路由 LLM 模型 (text_optimize)
    target_model_id = request.model_profile_id or (preset.default_model_profile_id if preset else None)
    model_profile, provider = resolve_model_for_capability(
        db,
        capability="text_optimize",
        manual_profile_id=target_model_id,
        scene="prompt_optimize",
    )

    api_key = CredentialManager.get_credential(provider.credential_ref) if provider.credential_ref else ""

    # 3. 构建 System Prompt
    system_rules = (
        "You are an expert AI image prompt engineer. Your job is to refine and expand the user's raw prompt "
        "into a descriptive, vivid, and aesthetically superior text-to-image prompt.\n"
        "Requirements:\n"
        "1. Faithfully preserve the user's core subjects, actions, and intent.\n"
        "2. Enrich with specific details: subject appearance, environment/background, lighting/mood, camera framing/angle, and visual style.\n"
        "3. Output ONLY the refined English prompt. Never include any greetings, quotes, markdown wrappers, or conversational explanations."
    )
    if preset and preset.system_rules:
        system_rules += f"\n\nStyle & Rule Guidance:\n{preset.system_rules}"
    if request.custom_instruction:
        system_rules += f"\n\nUser Custom Instruction:\n{request.custom_instruction}"

    messages = [
        {"role": "system", "content": system_rules},
        {"role": "user", "content": f"Please optimize this prompt for text-to-image generation:\n{raw_prompt}"},
    ]

    settings_dict = json.loads(provider.settings_json) if provider.settings_json else {}
    adapter = OpenAICompatibleAdapter(
        base_url=provider.base_url,
        api_key=api_key,
        model_id=model_profile.model_id,
        settings=settings_dict,
    )

    refined = await adapter.chat_complete(messages=messages, temperature=0.7)
    # 清理多余引号或前缀
    cleaned = refined.strip().strip('"').strip("'")
    if cleaned.lower().startswith("optimized prompt:"):
        cleaned = cleaned[len("optimized prompt:"):].strip()

    # 如果预设有 prompt_suffix，可按需追加（若大模型尚未融合）
    if preset and preset.default_params.get("prompt_suffix"):
        suffix = str(preset.default_params["prompt_suffix"]).strip()
        if suffix and not cleaned.endswith(suffix):
            cleaned = f"{cleaned}{suffix}"

    return PromptOptimizeResult(
        original_prompt=raw_prompt,
        optimized_prompt=cleaned,
        model_profile_id=model_profile.id,
        model_name=model_profile.name,
        provider_name=provider.name,
        diff_summary=f"从 {len(raw_prompt)} 字符扩写至 {len(cleaned)} 字符",
    )
