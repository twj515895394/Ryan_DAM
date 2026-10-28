from __future__ import annotations

import io
from PIL import Image

from backend.app.services.ai.image_canvas import (
    adapt_reference_canvas_for_aspect_ratio,
    align_output_dimensions,
    parse_aspect_ratio,
    parse_target_dimensions,
    get_edge_fill_color,
)


def _create_test_image(
    size: tuple[int, int],
    color: tuple[int, int, int] | tuple[int, int, int, int] = (100, 150, 200),
    mode: str = "RGB",
) -> bytes:
    im = Image.new(mode, size, color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_parse_aspect_ratio():
    assert abs(parse_aspect_ratio("16:9") - 16 / 9) < 1e-4
    assert abs(parse_aspect_ratio("16：9") - 16 / 9) < 1e-4
    assert abs(parse_aspect_ratio("9:16") - 9 / 16) < 1e-4
    assert abs(parse_aspect_ratio("1:1") - 1.0) < 1e-4
    assert abs(parse_aspect_ratio("4:3") - 4 / 3) < 1e-4

    # Fallback to size
    assert abs(parse_aspect_ratio(None, "1920x1080") - 16 / 9) < 1e-4
    assert abs(parse_aspect_ratio(None, "1024*1024") - 1.0) < 1e-4

    # Invalid
    assert parse_aspect_ratio(None, None) is None
    assert parse_aspect_ratio("invalid", "") is None
    assert parse_aspect_ratio("0:10") is None


def test_parse_target_dimensions():
    assert parse_target_dimensions("1920x1080") == (1920, 1080)
    assert parse_target_dimensions(" 1280 * 720 ") == (1280, 720)
    assert parse_target_dimensions("1024X1024") == (1024, 1024)
    assert parse_target_dimensions("") is None
    assert parse_target_dimensions(None) is None
    assert parse_target_dimensions("abc") is None
    assert parse_target_dimensions("-100x200") is None


def test_get_edge_fill_color():
    im = Image.new("RGB", (100, 100), (45, 65, 85))
    fill = get_edge_fill_color(im)
    assert fill == (45, 65, 85)


def test_adapt_reference_canvas_narrow_to_wide():
    # 4:3 (1448x1086) -> 16:9 (~1.7778)
    img_bytes = _create_test_image((1448, 1086), color=(200, 200, 200))
    adapted_bytes, _ = adapt_reference_canvas_for_aspect_ratio(
        image_bytes=img_bytes,
        target_ratio=16 / 9,
    )
    adapted_im = Image.open(io.BytesIO(adapted_bytes))
    w, h = adapted_im.size
    assert h == 1086
    assert abs((w / h) - (16 / 9)) < 0.01
    assert w > 1448  # Widen canvas


def test_adapt_reference_canvas_wide_to_tall():
    # 16:9 (1920x1080) -> 1:1
    img_bytes = _create_test_image((1920, 1080), color=(120, 130, 140))
    adapted_bytes, _ = adapt_reference_canvas_for_aspect_ratio(
        image_bytes=img_bytes,
        target_ratio=1.0,
    )
    adapted_im = Image.open(io.BytesIO(adapted_bytes))
    w, h = adapted_im.size
    assert w == 1920
    assert h == 1920
    assert abs((w / h) - 1.0) < 1e-4


def test_adapt_reference_canvas_already_matches():
    # 16:9 to 16:9: returns original bytes
    img_bytes = _create_test_image((1920, 1080))
    adapted_bytes, _ = adapt_reference_canvas_for_aspect_ratio(
        image_bytes=img_bytes,
        target_ratio=16 / 9,
        threshold=0.02,
    )
    assert adapted_bytes == img_bytes


def test_adapt_reference_canvas_with_mask():
    img_bytes = _create_test_image((800, 600))
    mask_bytes = _create_test_image((800, 600), color=0, mode="L")

    adapted_img, adapted_mask = adapt_reference_canvas_for_aspect_ratio(
        image_bytes=img_bytes,
        mask_bytes=mask_bytes,
        target_ratio=16 / 9,
    )
    assert adapted_mask is not None
    mask_im = Image.open(io.BytesIO(adapted_mask))
    img_im = Image.open(io.BytesIO(adapted_img))
    assert mask_im.size == img_im.size
    # Newly expanded left and right borders should be 255 (inpaint area)
    assert mask_im.getpixel((0, 300)) == 255
    # Center original area should remain 0
    center_x = mask_im.width // 2
    center_y = mask_im.height // 2
    assert mask_im.getpixel((center_x, center_y)) == 0


def test_align_output_dimensions_matching_ratio():
    # Model returned 1672x941 (16:9), user requested 1920x1080
    raw_img = _create_test_image((1672, 941))
    aligned_bytes = align_output_dimensions(raw_img, target_size_str="1920x1080")
    aligned_im = Image.open(io.BytesIO(aligned_bytes))
    assert aligned_im.size == (1920, 1080)


def test_align_output_dimensions_different_ratio_no_distortion():
    # Model returned 1024x1024 (1:1), user requested 1920x1080 (16:9)
    # Ratio difference is large, should not distort
    raw_img = _create_test_image((1024, 1024))
    aligned_bytes = align_output_dimensions(raw_img, target_size_str="1920x1080")
    aligned_im = Image.open(io.BytesIO(aligned_bytes))
    assert aligned_im.size == (1024, 1024)
