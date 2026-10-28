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
    # ── 图生图与参考图编辑预设 (image_edit) ──────────────────────────────────
    {
        "code": "edit_character_retouch",
        "name": "角色重绘与换装 (Character Redress)",
        "description": "基于参考图面部与体态，精准保持角色五官一致，更换服装与发型配饰",
        "creation_mode": "image_edit",
        "system_rules": "严格保持参考图中人物的五官比例、面容特征与基本身材比例一致。根据用户新 Prompt 的要求更换服饰设计、微调发型姿态或微表情，画面过渡自然，无任何拼接撕裂感。",
        "default_params": {
            "prompt_suffix": ", consistent face, high fidelity character likeness, natural lighting, highly detailed clothing texture, masterpiece",
            "negative_prompt": "face distortion, bad anatomy, deformed eyes, mismatched facial features, low quality",
        },
        "sort_order": 11,
    },
    {
        "code": "edit_anime_remix",
        "name": "日漫次元转换 (Anime & Comic Remix)",
        "description": "提取参考图构图透视与人物动作轮廓，转变为清透细腻的新海诚日漫手绘风",
        "creation_mode": "image_edit",
        "system_rules": "保留原参考图的主体轮廓、姿势动态与空间透视关系，全面重构为精致清透的日本动漫电影风格。强化干净手绘线稿、通透高光与水彩漫反射氛围。",
        "default_params": {
            "prompt_suffix": ", Makoto Shinkai style, vibrant colors, clean delicate anime lineart, beautiful anime skies and lighting, masterpiece illustration",
            "negative_prompt": "photorealistic, western comic, muddy, 3d plastic, lowres",
        },
        "sort_order": 12,
    },
    {
        "code": "edit_relight_atmosphere",
        "name": "光影氛围重构 (Relighting & Mood Shift)",
        "description": "保留参考图主体对象与空间布局，重新渲染电影级全局光影（如日落金辉/暗夜霓虹）",
        "creation_mode": "image_edit",
        "system_rules": "保留参考图中主体的物理结构与场景布局，重新进行电影级光影重新布光与色彩基调渲染。产生逼真自然的阴影投射与环境反射。",
        "default_params": {
            "prompt_suffix": ", dramatic cinematic lighting, volumetric rays, rich color atmosphere, realistic shadows and highlights, 8k resolution",
            "negative_prompt": "flat lighting, overexposed, washed out, low contrast, blurry",
        },
        "sort_order": 13,
    },
    {
        "code": "edit_detail_enhance",
        "name": "微表面质感增强 (Micro-Detail Enhancement)",
        "description": "原构图与内容完全不变，针对微表面纹理、毛孔、织物纤维与清晰度进行高保真增强",
        "creation_mode": "image_edit",
        "system_rules": "极其严格忠实于参考图的原始内容、构图与色彩，只针对微表面纹理、皮肤毛孔细节、织物纹路、金属边缘反光与清晰度进行高保真增强。",
        "default_params": {
            "prompt_suffix": ", extremely detailed micro-surface textures, sharp focus, 8k uhd, realistic skin pores, fine fabric weave, crystal clear",
            "negative_prompt": "blur, noisy, smooth plastic skin, low resolution, artifact",
        },
        "sort_order": 14,
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


def reset_creation_preset(db: Session, preset_id: int) -> AiCreationPreset:
    """将修改过的内置创作预设一键恢复为系统默认初始状态。"""
    preset = get_creation_preset(db, preset_id)
    if not preset.is_builtin or not preset.code:
        raise ApiError(code="cannot_reset_custom", message="只有系统内置创作预设可重置恢复默认", status_code=400)

    matched = next((item for item in BUILTIN_CREATION_PRESETS if item["code"] == preset.code), None)
    if not matched:
        raise ApiError(code="builtin_preset_missing", message=f"未找到预设 code={preset.code} 的系统初始配置", status_code=404)

    preset.name = matched["name"]
    preset.description = matched["description"]
    preset.creation_mode = matched["creation_mode"]
    preset.system_rules = matched["system_rules"]
    preset.default_params_json = json.dumps(matched["default_params"], ensure_ascii=False)
    preset.sort_order = matched["sort_order"]
    preset.enabled = True

    db.commit()
    db.refresh(preset)
    return preset


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
    lang = (request.language or "zh").strip().lower()
    has_custom = bool(request.custom_instruction and request.custom_instruction.strip())

    if lang == "en":
        if has_custom:
            system_rules = (
                "You are an expert AI image prompt engineer.\n"
                "Your task is to refine and modify the user's 【existing base prompt】 by strictly incorporating the user's 【incremental modification requirements】.\n"
                "Requirements:\n"
                "1. Faithfully keep the core essence of the base prompt while accurately applying all requested changes (subject traits, style, lighting, environment, additions/removals).\n"
                "2. Ensure the resulting prompt is coherent, descriptive, and aesthetically superior for text-to-image generation.\n"
                "3. Output ONLY the refined English prompt. Never include any greetings, quotes, markdown wrappers, or conversational explanations."
            )
            user_prompt_instruction = (
                f"【Existing Base Prompt】:\n{raw_prompt}\n\n"
                f"【Modification & Refinement Requirements】:\n{request.custom_instruction.strip()}\n\n"
                "Please generate the refined text-to-image prompt incorporating these modifications (output in English):"
            )
        else:
            system_rules = (
                "You are an expert AI image prompt engineer. Your job is to refine and expand the user's raw prompt "
                "into a descriptive, vivid, and aesthetically superior text-to-image prompt.\n"
                "Requirements:\n"
                "1. Faithfully preserve the user's core subjects, actions, and intent.\n"
                "2. Enrich with specific details: subject appearance, environment/background, lighting/mood, camera framing/angle, and visual style.\n"
                "3. Output ONLY the refined English prompt. Never include any greetings, quotes, markdown wrappers, or conversational explanations."
            )
            user_prompt_instruction = f"Please optimize this prompt for text-to-image generation (output in English):\n{raw_prompt}"
    else:
        if has_custom:
            system_rules = (
                "你是一位顶尖的 AI 图像提示词（Prompt）专家与视觉美学导师。\n"
                "你的核心任务是在用户【已有的基础提示词】之上，精准结合用户提出的【增量修改与优化要求】，重新编排输出修改重塑后的高品质生图提示词。\n"
                "核心要求：\n"
                "1. 严格以已有的基础提示词为画面基底，忠实融入用户的增量修改要求（例如主体服饰变换、增加特定元素、光影重构、艺术风格调整等）。\n"
                "2. 保持画面元素之间的高度协调统一与画面生动性，光影细腻、细节丰富。\n"
                "3. 【绝对语言约束】：必须且仅使用【中文】输出修改后的提示词正文！坚决禁止输出纯英文段落（专业生图参数或特定专业英文词汇如 8k/Fujifilm 可合理保留，但全篇必须以中文自然叙述为主）。\n"
                "4. 严禁输出任何问候语、说明前缀（如'修改后的提示词：'）、引号、Markdown 标记或解释性文字，直接输出可直接用于生图的提示词正文本体。"
            )
            user_prompt_instruction = (
                f"【已有基础提示词】：\n{raw_prompt}\n\n"
                f"【用户的修改与优化要求】：\n{request.custom_instruction.strip()}\n\n"
                "请基于上述基础提示词并充分融合用户的修改要求，生成最终的生图提示词（严格要求中文输出）："
            )
        else:
            system_rules = (
                "你是一位顶尖的 AI 图像提示词（Prompt）专家与视觉美学导师。你的核心职责是将用户的简短想法或原始提示词，"
                "扩写润色为画面生动、光影细腻、细节丰富的高品质生图提示词。\n"
                "核心要求：\n"
                "1. 忠实还原用户的核心画面主体、动作与意图，严禁擅自偏离主题。\n"
                "2. 深度扩充视觉细节：主体外观面貌、服饰材质、所处空间与背景环境、光影质感、镜头景深构图与艺术审美倾向。\n"
                "3. 【绝对语言约束】：必须且仅使用【中文】输出润色后的提示词正文！坚决禁止输出纯英文段落（专业生图参数或特定专业英文词汇如 8k/Fujifilm 可合理保留，但全篇必须以中文自然叙述为主）。\n"
                "4. 严禁输出任何问候语、说明前缀（如'润色后的提示词：'）、引号、Markdown 标记或解释性文字，直接输出可直接用于生图的提示词正文本体。"
            )
            user_prompt_instruction = f"请将以下生图提示词进行专业扩写与美学润色（严格要求使用中文输出）：\n{raw_prompt}"

    if preset and preset.system_rules:
        prefix = "Style & Rule Guidance:" if lang == "en" else "预设风格与美学指引："
        system_rules += f"\n\n{prefix}\n{preset.system_rules}"

    messages = [
        {"role": "system", "content": system_rules},
        {"role": "user", "content": user_prompt_instruction},
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
