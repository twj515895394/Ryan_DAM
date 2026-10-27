from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

# 匹配 markdown 图片语法：![alt](url)，url 为 data URL 或 http(s) 链接
MARKDOWN_IMAGE_RE = re.compile(
    r"!\[[^\]]*\]\(\s*(data:image/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=]+|https?://[^)\s]+)\s*\)"
)

# 1x1 transparent PNG for lightweight probe
TINY_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
TINY_PNG_DATA_URL = f"data:image/png;base64,{base64.b64encode(TINY_PNG_BYTES).decode('ascii')}"

CAPABILITY_TEXT_OPTIMIZE = "text_optimize"
CAPABILITY_IMAGE_UNDERSTAND = "image_understand"
CAPABILITY_IMAGE_GENERATE = "image_generate"
CAPABILITY_IMAGE_EDIT = "image_edit"

SUPPORTED_CAPABILITIES = (
    CAPABILITY_TEXT_OPTIMIZE,
    CAPABILITY_IMAGE_UNDERSTAND,
    CAPABILITY_IMAGE_GENERATE,
    CAPABILITY_IMAGE_EDIT,
)


@dataclass
class ProbeResult:
    capability: str
    supported: bool
    latency_ms: int
    model_id: str
    message: str
    error_code: str | None = None
    output_sample: str | None = None
    raw_details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "supported": self.supported,
            "latency_ms": self.latency_ms,
            "model_id": self.model_id,
            "message": self.message,
            "error_code": self.error_code,
            "output_sample": self.output_sample,
            "raw_details": self.raw_details,
        }


def normalize_base_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    # If the user enters a root url without /v1, and it doesn't end with a version segment, keep as is
    return cleaned


def parse_error_response(status_code: int, response_text: str) -> tuple[str, str]:
    """Parse standard OpenAI or third-party error payload into (error_code, error_message)."""
    import json

    msg = f"HTTP {status_code}"
    code = "api_error"

    try:
        data = json.loads(response_text)
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                msg = err.get("message") or msg
                code = err.get("code") or code
            elif isinstance(err, str):
                msg = err
            elif "message" in data:
                msg = str(data["message"])
    except Exception:
        if response_text:
            msg = response_text[:200]

    # Map status codes to canonical error codes
    lowered_msg = msg.lower()
    if status_code in (401, 403):
        return "unauthorized", "API Key 无效或缺少访问权限。"
    if status_code == 404:
        if "model" in lowered_msg:
            return "model_not_found", f"模型不存在或当前端点不支持：{msg}"
        return "capability_unsupported", f"当前服务不支持此能力端点 (HTTP 404)：{msg}"
    if status_code in (405, 501):
        return "capability_unsupported", f"当前服务不支持此方法或端点 (HTTP {status_code})：{msg}"
    if status_code == 429:
        return "rate_limit", f"已触发服务限流或配额已耗尽：{msg}"
    if status_code == 422:
        return "invalid_parameter", f"请求参数校验失败：{msg}"
    if status_code >= 500:
        return "server_error", f"服务提供商服务器异常 (HTTP {status_code})：{msg}"

    return code, msg


def probe_text_optimize(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model_id: str,
    *,
    timeout: float = 15.0,
) -> ProbeResult:
    """Probe text LLM capability via /chat/completions."""
    start_time = time.perf_counter()
    url = f"{normalize_base_url(base_url)}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Reply with only 'ok'."},
            {"role": "user", "content": "ping"},
        ],
        "max_tokens": 10,
        "temperature": 0.0,
    }

    try:
        resp = client.post(url, json=payload, headers=headers, timeout=timeout)
        latency = int((time.perf_counter() - start_time) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices") or []
            content = choices[0].get("message", {}).get("content", "").strip() if choices else ""
            return ProbeResult(
                capability=CAPABILITY_TEXT_OPTIMIZE,
                supported=True,
                latency_ms=latency,
                model_id=model_id,
                message="文本优化与对话接口测试通过",
                output_sample=content[:100],
            )
        err_code, err_msg = parse_error_response(resp.status_code, resp.text)
        return ProbeResult(
            capability=CAPABILITY_TEXT_OPTIMIZE,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message=err_msg,
            error_code=err_code,
            raw_details={"status_code": resp.status_code},
        )
    except httpx.TimeoutException:
        latency = int((time.perf_counter() - start_time) * 1000)
        return ProbeResult(
            capability=CAPABILITY_TEXT_OPTIMIZE,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message="请求连接超时，请检查 Base URL 网络连通性。",
            error_code="timeout",
        )
    except Exception as exc:
        latency = int((time.perf_counter() - start_time) * 1000)
        return ProbeResult(
            capability=CAPABILITY_TEXT_OPTIMIZE,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message=f"网络请求失败：{exc}",
            error_code="connection_error",
        )


def probe_image_understand(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model_id: str,
    *,
    data_url: str = TINY_PNG_DATA_URL,
    timeout: float = 20.0,
) -> ProbeResult:
    """Probe multimodal vision capability via /chat/completions with image_url."""
    start_time = time.perf_counter()
    url = f"{normalize_base_url(base_url)}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in 5 words or less."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 30,
    }

    try:
        resp = client.post(url, json=payload, headers=headers, timeout=timeout)
        latency = int((time.perf_counter() - start_time) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices") or []
            content = choices[0].get("message", {}).get("content", "").strip() if choices else ""
            return ProbeResult(
                capability=CAPABILITY_IMAGE_UNDERSTAND,
                supported=True,
                latency_ms=latency,
                model_id=model_id,
                message="图片视觉反推与理解接口测试通过",
                output_sample=content[:100],
            )
        err_code, err_msg = parse_error_response(resp.status_code, resp.text)
        # Check if the model explicitly does not support vision
        lowered = err_msg.lower()
        if "vision" in lowered or "image" in lowered or "multimodal" in lowered or resp.status_code in (400, 404):
            err_code = "capability_unsupported"
            err_msg = f"该模型或端点不支持视觉多模态输入：{err_msg}"
        return ProbeResult(
            capability=CAPABILITY_IMAGE_UNDERSTAND,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message=err_msg,
            error_code=err_code,
            raw_details={"status_code": resp.status_code},
        )
    except httpx.TimeoutException:
        latency = int((time.perf_counter() - start_time) * 1000)
        return ProbeResult(
            capability=CAPABILITY_IMAGE_UNDERSTAND,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message="视觉请求连接超时。",
            error_code="timeout",
        )
    except Exception as exc:
        latency = int((time.perf_counter() - start_time) * 1000)
        return ProbeResult(
            capability=CAPABILITY_IMAGE_UNDERSTAND,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message=f"视觉请求失败：{exc}",
            error_code="connection_error",
        )


def extract_images_from_payload(data: dict[str, Any]) -> list[str]:
    """Extract image URLs / data URLs from either /images/generations format or Chat completions format."""
    results: list[str] = []
    # 1. Standard OpenAI Images format
    items = data.get("data")
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                url = it.get("url") or it.get("b64_json")
                if url:
                    results.append(url)
        if results:
            return results

    # 2. Chat completions format (e.g. Gemini / OpenRouter / local proxy)
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") or {}
        # 2a: message.images: [{image_url: {url}}]
        images_list = msg.get("images") or []
        for it in images_list:
            if isinstance(it, dict):
                img_url = it.get("image_url", {}).get("url") or it.get("url")
                if img_url:
                    results.append(img_url)
        # 2b: Markdown embedded image in message.content
        if not results:
            content = msg.get("content") or ""
            if isinstance(content, str):
                results.extend(MARKDOWN_IMAGE_RE.findall(content))

    return results


def probe_image_generate(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model_id: str,
    *,
    timeout: float = 30.0,
) -> ProbeResult:
    """Probe image generation capability via /images/generations or chat completions fallback."""
    start_time = time.perf_counter()
    normalized = normalize_base_url(base_url)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    is_gemini_chat = "gemini" in model_id.lower()

    if is_gemini_chat:
        url = f"{normalized}/chat/completions"
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "Draw a small blue dot"}],
            "size": "1024x1024",
        }
    else:
        url = f"{normalized}/images/generations"
        payload = {
            "model": model_id,
            "prompt": "minimal test point",
            "n": 1,
            "size": "1024x1024",
        }

    try:
        resp = client.post(url, json=payload, headers=headers, timeout=timeout)
        latency = int((time.perf_counter() - start_time) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            images = extract_images_from_payload(data)
            first_url = images[0] if images else ""
            if not images:
                return ProbeResult(
                    capability=CAPABILITY_IMAGE_GENERATE,
                    supported=False,
                    latency_ms=latency,
                    model_id=model_id,
                    message="接口返回成功但响应中未检测到图片输出数据",
                    error_code="invalid_response",
                    raw_details={"response": data},
                )
            return ProbeResult(
                capability=CAPABILITY_IMAGE_GENERATE,
                supported=True,
                latency_ms=latency,
                model_id=model_id,
                message="图片生成接口测试通过",
                output_sample=first_url[:80],
            )
        err_code, err_msg = parse_error_response(resp.status_code, resp.text)
        if resp.status_code in (404, 405):
            err_code = "capability_unsupported"
            err_msg = f"该第三方服务不支持此图片生成接口端点 ({url})。"
        return ProbeResult(
            capability=CAPABILITY_IMAGE_GENERATE,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message=err_msg,
            error_code=err_code,
            raw_details={"status_code": resp.status_code},
        )
    except httpx.TimeoutException:
        latency = int((time.perf_counter() - start_time) * 1000)
        return ProbeResult(
            capability=CAPABILITY_IMAGE_GENERATE,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message="图片生成接口请求超时。",
            error_code="timeout",
        )
    except Exception as exc:
        latency = int((time.perf_counter() - start_time) * 1000)
        return ProbeResult(
            capability=CAPABILITY_IMAGE_GENERATE,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message=f"图片生成接口请求失败：{exc}",
            error_code="connection_error",
        )


def probe_image_edit(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model_id: str,
    *,
    sample_bytes: bytes = TINY_PNG_BYTES,
    timeout: float = 30.0,
) -> ProbeResult:
    """Probe image editing capability via /images/edits."""
    start_time = time.perf_counter()
    url = f"{normalize_base_url(base_url)}/images/edits"
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {
        "image": ("test.png", sample_bytes, "image/png"),
    }
    data = {
        "model": model_id,
        "prompt": "minimal test",
        "n": 1,
        "size": "1024x1024",
    }

    try:
        resp = client.post(url, data=data, files=files, headers=headers, timeout=timeout)
        latency = int((time.perf_counter() - start_time) * 1000)
        if resp.status_code == 200:
            res_data = resp.json()
            items = res_data.get("data") or []
            sample = items[0].get("url") or items[0].get("b64_json", "")[:30] if items else ""
            return ProbeResult(
                capability=CAPABILITY_IMAGE_EDIT,
                supported=True,
                latency_ms=latency,
                model_id=model_id,
                message="图片编辑接口 (/images/edits) 测试通过",
                output_sample=sample[:80],
            )
        err_code, err_msg = parse_error_response(resp.status_code, resp.text)
        if resp.status_code in (404, 405):
            err_code = "capability_unsupported"
            err_msg = "该第三方服务不支持标准图片编辑接口 (/images/edits)。"
        return ProbeResult(
            capability=CAPABILITY_IMAGE_EDIT,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message=err_msg,
            error_code=err_code,
            raw_details={"status_code": resp.status_code},
        )
    except httpx.TimeoutException:
        latency = int((time.perf_counter() - start_time) * 1000)
        return ProbeResult(
            capability=CAPABILITY_IMAGE_EDIT,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message="图片编辑接口请求超时。",
            error_code="timeout",
        )
    except Exception as exc:
        latency = int((time.perf_counter() - start_time) * 1000)
        return ProbeResult(
            capability=CAPABILITY_IMAGE_EDIT,
            supported=False,
            latency_ms=latency,
            model_id=model_id,
            message=f"图片编辑接口请求失败：{exc}",
            error_code="connection_error",
        )


def probe_all_capabilities(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model_mapping: dict[str, str],
    capabilities: list[str] | None = None,
) -> dict[str, ProbeResult]:
    """
    Probe multiple capabilities with given model IDs.
    `model_mapping` maps capability name to model_id.
    """
    targets = capabilities or list(SUPPORTED_CAPABILITIES)
    results: dict[str, ProbeResult] = {}

    for cap in targets:
        model_id = model_mapping.get(cap)
        if not model_id:
            results[cap] = ProbeResult(
                capability=cap,
                supported=False,
                latency_ms=0,
                model_id="",
                message="未配置该能力对应的模型 ID",
                error_code="model_unconfigured",
            )
            continue

        if cap == CAPABILITY_TEXT_OPTIMIZE:
            results[cap] = probe_text_optimize(client, base_url, api_key, model_id)
        elif cap == CAPABILITY_IMAGE_UNDERSTAND:
            results[cap] = probe_image_understand(client, base_url, api_key, model_id)
        elif cap == CAPABILITY_IMAGE_GENERATE:
            results[cap] = probe_image_generate(client, base_url, api_key, model_id)
        elif cap == CAPABILITY_IMAGE_EDIT:
            results[cap] = probe_image_edit(client, base_url, api_key, model_id)

    return results
