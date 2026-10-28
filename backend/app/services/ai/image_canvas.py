from __future__ import annotations

import io
import logging
from typing import Tuple

from PIL import Image

logger = logging.getLogger(__name__)


def parse_aspect_ratio(
    aspect_ratio_str: str | None = None,
    size_str: str | None = None,
) -> float | None:
    """从 aspect_ratio 字符串（如 '16:9'）或尺寸分辨率字符串（如 '1920x1080'）解析目标宽高比。"""
    if aspect_ratio_str:
        normalized = aspect_ratio_str.replace("：", ":").strip()
        parts = normalized.split(":")
        if len(parts) == 2:
            try:
                w_f = float(parts[0])
                h_f = float(parts[1])
                if w_f > 0 and h_f > 0:
                    return w_f / h_f
            except ValueError:
                pass

    if size_str:
        dims = parse_target_dimensions(size_str)
        if dims and dims[0] > 0 and dims[1] > 0:
            return dims[0] / dims[1]

    return None


def parse_target_dimensions(size_str: str | None) -> Tuple[int, int] | None:
    """解析尺寸字符串为整型宽高 (width, height)。支持 '1920x1080', '1920*1080', '1920X1080' 等格式。"""
    if not size_str:
        return None
    cleaned = size_str.strip().lower()
    for sep in ("x", "*"):
        if sep in cleaned:
            parts = cleaned.split(sep)
            if len(parts) == 2:
                try:
                    w = int(parts[0].strip())
                    h = int(parts[1].strip())
                    if w > 0 and h > 0:
                        return w, h
                except ValueError:
                    pass
    return None


def get_edge_fill_color(image: Image.Image) -> tuple[int, int, int]:
    """采样图像四周边缘像素，计算最契合原图背景的平滑补色 (RGB)。"""
    if image.mode != "RGB":
        image = image.convert("RGB")

    w, h = image.size
    pixels: list[tuple[int, int, int]] = []
    step_x = max(1, w // 20)
    step_y = max(1, h // 20)

    for x in range(0, w, step_x):
        pixels.append(image.getpixel((x, 0)))  # 顶边
        pixels.append(image.getpixel((x, h - 1)))  # 底边
    for y in range(0, h, step_y):
        pixels.append(image.getpixel((0, y)))  # 左边
        pixels.append(image.getpixel((w - 1, y)))  # 右边

    if not pixels:
        return (255, 255, 255)

    avg_r = int(sum(p[0] for p in pixels) / len(pixels))
    avg_g = int(sum(p[1] for p in pixels) / len(pixels))
    avg_b = int(sum(p[2] for p in pixels) / len(pixels))
    return (avg_r, avg_g, avg_b)


def adapt_reference_canvas_for_aspect_ratio(
    image_bytes: bytes,
    mask_bytes: bytes | None = None,
    target_ratio: float | None = None,
    threshold: float = 0.03,
) -> tuple[bytes, bytes | None]:
    """在图生图/图像编辑模式下，若参考图原始比例与用户指定的目标画幅比例不一致，

    预先将参考图画布扩展居中（Letterbox/Pillarbox），使送入生图模型的画布与目标比例严格一致。
    同时，若存在遮罩层（mask），一并扩展遮罩画布并在新增填充区域标记为编辑区（255）。
    """
    if not target_ratio or target_ratio <= 0:
        return image_bytes, mask_bytes

    try:
        orig = Image.open(io.BytesIO(image_bytes))
    except Exception as err:
        logger.warning(f"无法读取参考图进行比例自适应解析: {err}")
        return image_bytes, mask_bytes

    orig_w, orig_h = orig.size
    if orig_w <= 0 or orig_h <= 0:
        return image_bytes, mask_bytes

    orig_ratio = orig_w / orig_h
    # 若比例差异在阈值内，直接返回
    if abs(orig_ratio - target_ratio) <= threshold:
        return image_bytes, mask_bytes

    has_alpha = orig.mode in ("RGBA", "LA") or (
        orig.mode == "P" and "transparency" in orig.info
    )

    if orig_ratio < target_ratio:
        # 参考图偏窄/偏高（例如 4:3 放入 16:9 目标），需要水平加宽画布
        new_w = int(round(orig_h * target_ratio))
        new_h = orig_h
        offset_x = (new_w - orig_w) // 2
        offset_y = 0
    else:
        # 参考图偏宽/偏矮（例如 16:9 放入 1:1 或 9:16 目标），需要垂直加高画布
        new_w = orig_w
        new_h = int(round(orig_w / target_ratio))
        offset_x = 0
        offset_y = (new_h - orig_h) // 2

    # 创建目标底板并居中贴入
    if has_alpha:
        canvas = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
        canvas.paste(orig.convert("RGBA"), (offset_x, offset_y))
    else:
        fill_color = get_edge_fill_color(orig)
        canvas = Image.new("RGB", (new_w, new_h), fill_color)
        canvas.paste(orig.convert("RGB"), (offset_x, offset_y))

    out_buf = io.BytesIO()
    canvas.save(out_buf, format="PNG")
    adapted_image_bytes = out_buf.getvalue()

    adapted_mask_bytes: bytes | None = None
    if mask_bytes:
        try:
            orig_mask = Image.open(io.BytesIO(mask_bytes)).convert("L")
            # 遮罩新扩展区域设为 255（重绘区），保证模型在该画幅区域自由生成
            mask_canvas = Image.new("L", (new_w, new_h), 255)
            mask_canvas.paste(orig_mask, (offset_x, offset_y))
            mask_buf = io.BytesIO()
            mask_canvas.save(mask_buf, format="PNG")
            adapted_mask_bytes = mask_buf.getvalue()
        except Exception as mask_err:
            logger.warning(f"扩展参考图遮罩层失败: {mask_err}")
            adapted_mask_bytes = mask_bytes

    logger.info(
        f"参考图画幅自适应完成: 原始 {orig_w}x{orig_h} (比例 {orig_ratio:.4f}) -> "
        f"自适应目标比例 {target_ratio:.4f}，新画布 {new_w}x{new_h}"
    )
    return adapted_image_bytes, adapted_mask_bytes


def align_output_dimensions(
    image_bytes: bytes,
    target_size_str: str | None = None,
    max_ratio_error: float = 0.05,
) -> bytes:
    """对生成模型返回的图像进行分辨率规格精确对其。

    若模型产出图像的宽高比与用户请求的目标分辨率（如 1920x1080）基本一致，
    但由于服务商分档策略返回了略小或略大尺寸（例如 1672x941），
    通过高保真 Lanczos 算法精确重采样至目标分辨率，确保用户获得符合预期的像素宽高。
    """
    if not target_size_str:
        return image_bytes

    target_dims = parse_target_dimensions(target_size_str)
    if not target_dims:
        return image_bytes

    target_w, target_h = target_dims
    if target_w <= 0 or target_h <= 0:
        return image_bytes

    try:
        im = Image.open(io.BytesIO(image_bytes))
    except Exception as err:
        logger.warning(f"无法读取输出图像进行尺寸校准: {err}")
        return image_bytes

    gen_w, gen_h = im.size
    if (gen_w, gen_h) == (target_w, target_h):
        return image_bytes

    gen_ratio = gen_w / gen_h
    target_ratio = target_w / target_h

    # 仅当宽高比误差在容差范围内时进行精确重采样（防止畸变）
    if abs(gen_ratio - target_ratio) <= max_ratio_error:
        resample_mode = (
            getattr(Image, "Resampling", Image).LANCZOS
            if hasattr(Image, "Resampling")
            else Image.LANCZOS
        )
        resized = im.resize((target_w, target_h), resample_mode)
        buf = io.BytesIO()
        out_format = im.format or "PNG"
        resized.save(buf, format=out_format)
        logger.info(
            f"生成图像尺寸校准完成: 原始输出 {gen_w}x{gen_h} -> 校准至目标分辨率 {target_w}x{target_h}"
        )
        return buf.getvalue()

    return image_bytes
