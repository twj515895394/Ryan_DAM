from __future__ import annotations

import base64
import logging
import re
from typing import Any
import httpx

from backend.app.core.errors import ApiError
from backend.app.services.ai.protocol_poc import normalize_base_url, parse_error_response

logger = logging.getLogger(__name__)

_MARKDOWN_IMAGE_RE = re.compile(r"!\[.*?\]\((data:image\/[^;]+;base64,[^)]+|https?:\/\/[^)]+)\)")


class OpenAICompatibleAdapter:
    """OpenAI 兼容协议客户端适配器，支持视觉反推、文本优化、生图与编辑调用。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        settings: dict | None = None,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.api_key = api_key
        self.model_id = model_id
        self.settings = settings or {}

    async def understand_image(
        self,
        image_base64_or_url: str,
        prompt: str,
        system_prompt: str | None = None,
        timeout: float = 60.0,
    ) -> str:
        """调用多模态 Vision 接口 (/chat/completions) 进行视觉理解与反推。"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_base64_or_url}},
        ]
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": 1500,
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException:
                raise ApiError(code="ai_timeout", message="视觉反推请求超时，请检查模型响应速度或网络", status_code=504)
            except Exception as e:
                raise ApiError(code="ai_network_error", message=f"请求失败：{e}", status_code=502)

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    raise ApiError(code="ai_empty_response", message="视觉模型未返回有效内容", status_code=502)
                content = choices[0].get("message", {}).get("content", "").strip()
                return content

            err_code, err_msg = parse_error_response(resp.status_code, resp.text)
            raise ApiError(code=err_code, message=err_msg, status_code=resp.status_code)

    async def chat_complete(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: float = 60.0,
    ) -> str:
        """调用文本对话接口 (/chat/completions) 进行提示词润色、扩写或文本生成。"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.settings and isinstance(self.settings.get("custom_headers"), dict):
            headers.update(self.settings["custom_headers"])

        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException:
                raise ApiError(code="ai_timeout", message="调用大模型对话接口超时，请稍后重试", status_code=504)
            except Exception as e:
                raise ApiError(code="ai_network_error", message=f"请求失败：{e}", status_code=502)

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    raise ApiError(code="ai_empty_response", message="大模型未返回有效内容", status_code=502)
                content = choices[0].get("message", {}).get("content", "").strip()
                return content

            err_code, err_msg = parse_error_response(resp.status_code, resp.text)
            raise ApiError(code=err_code, message=err_msg, status_code=resp.status_code)

    async def generate_images(
        self,
        prompt: str,
        n: int = 1,
        size: str = "1024x1024",
        adapter_kind: str = "openai_standard",
        extra_params: dict | None = None,
        timeout: float = 120.0,
    ) -> list[bytes]:
        """根据模型 adapter_kind 调用对应生图接口并返回解码后的原始图片二进制列表。"""
        if adapter_kind == "openai_chat_markdown":
            return await self._generate_via_chat(
                prompt=prompt,
                n=n,
                size=size,
                extra_params=extra_params,
                timeout=timeout,
            )
        return await self._generate_via_images_api(
            prompt=prompt,
            n=n,
            size=size,
            extra_params=extra_params,
            timeout=timeout,
        )

    async def _generate_via_images_api(
        self,
        prompt: str,
        n: int = 1,
        size: str = "1024x1024",
        extra_params: dict | None = None,
        timeout: float = 120.0,
    ) -> list[bytes]:
        """标准 OpenAI `/images/generations` 路由。"""
        url = f"{self.base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model_id,
            "prompt": prompt,
            "n": n,
            "size": size,
            "response_format": "b64_json",
        }
        if extra_params:
            payload.update(extra_params)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException:
                raise ApiError(code="ai_timeout", message="文生图请求超时，请检查模型响应速度或网络", status_code=504)
            except Exception as e:
                raise ApiError(code="ai_network_error", message=f"请求失败：{e}", status_code=502)

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data") or []
                if not items:
                    raise ApiError(code="ai_empty_response", message="文生图模型未返回任何图像数据", status_code=502)

                results: list[bytes] = []
                for item in items:
                    b64 = item.get("b64_json")
                    if b64:
                        results.append(base64.b64decode(b64))
                    elif item.get("url"):
                        # 从返回的短期 URL 获取
                        try:
                            img_resp = await client.get(item["url"], timeout=60.0)
                            if img_resp.status_code == 200:
                                results.append(img_resp.content)
                        except Exception as dl_err:
                            raise ApiError(code="ai_download_error", message=f"下载生成图片失败：{dl_err}", status_code=502)

                if not results:
                    raise ApiError(code="ai_empty_response", message="未解析出有效图像数据", status_code=502)
                return results[:n]

            err_code, err_msg = parse_error_response(resp.status_code, resp.text)
            raise ApiError(code=err_code, message=err_msg, status_code=resp.status_code)

    async def _generate_via_chat(
        self,
        prompt: str,
        n: int = 1,
        size: str = "1024x1024",
        extra_params: dict | None = None,
        timeout: float = 120.0,
    ) -> list[bytes]:
        """兼容多模态 Chat 路由（如部分网关中含 Gemini 或 markdown base64 返回）。"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "size": size,
        }
        if extra_params:
            payload.update(extra_params)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException:
                raise ApiError(code="ai_timeout", message="文生图请求超时", status_code=504)
            except Exception as e:
                raise ApiError(code="ai_network_error", message=f"请求失败：{e}", status_code=502)

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    raise ApiError(code="ai_empty_response", message="模型未返回有效内容", status_code=502)
                message = choices[0].get("message", {})

                # 兼容 1: message.images [{image_url: {url}}]
                images_list = message.get("images") or []
                urls: list[str] = []
                for it in images_list:
                    u = it.get("image_url", {}).get("url")
                    if u:
                        urls.append(u)

                # 兼容 2: markdown image regex
                if not urls:
                    content = message.get("content", "")
                    urls = _MARKDOWN_IMAGE_RE.findall(content)

                results: list[bytes] = []
                for u in urls:
                    if u.startswith("data:image/"):
                        _, encoded = u.split(",", 1)
                        results.append(base64.b64decode(encoded))
                    elif u.startswith("http"):
                        img_resp = await client.get(u, timeout=60.0)
                        if img_resp.status_code == 200:
                            results.append(img_resp.content)

                if not results:
                    raise ApiError(code="ai_empty_response", message="Chat 生图响应中未找到图片数据", status_code=502)
                return results[:n]

            err_code, err_msg = parse_error_response(resp.status_code, resp.text)
            raise ApiError(code=err_code, message=err_msg, status_code=resp.status_code)

    async def edit_image(
        self,
        image_bytes: bytes,
        prompt: str,
        mask_bytes: bytes | None = None,
        n: int = 1,
        size: str = "1024x1024",
        adapter_kind: str = "openai_standard",
        extra_params: dict | None = None,
        timeout: float = 120.0,
    ) -> list[bytes]:
        """调用模型图像编辑 / 图生图接口 (/images/edits 或多模态 Chat)。"""
        if adapter_kind == "openai_chat_markdown":
            return await self._edit_via_chat(
                image_bytes=image_bytes,
                prompt=prompt,
                mask_bytes=mask_bytes,
                n=n,
                size=size,
                extra_params=extra_params,
                timeout=timeout,
            )
        return await self._edit_via_images_api(
            image_bytes=image_bytes,
            prompt=prompt,
            mask_bytes=mask_bytes,
            n=n,
            size=size,
            extra_params=extra_params,
            timeout=timeout,
        )

    async def _edit_via_images_api(
        self,
        image_bytes: bytes,
        prompt: str,
        mask_bytes: bytes | None = None,
        n: int = 1,
        size: str = "1024x1024",
        extra_params: dict | None = None,
        timeout: float = 120.0,
    ) -> list[bytes]:
        """标准 OpenAI `/images/edits` 接口。"""
        url = f"{self.base_url}/images/edits"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        files = {
            "image": ("image.png", image_bytes, "image/png"),
        }
        if mask_bytes:
            files["mask"] = ("mask.png", mask_bytes, "image/png")

        data: dict[str, Any] = {
            "model": self.model_id,
            "prompt": prompt,
            "n": str(n),
            "size": size,
            "response_format": "b64_json",
        }
        if extra_params:
            for k, v in extra_params.items():
                data[k] = str(v)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(url, data=data, files=files, headers=headers)
            except httpx.TimeoutException:
                raise ApiError(code="ai_timeout", message="图生图编辑请求超时，请检查模型响应速度或网络", status_code=504)
            except Exception as e:
                raise ApiError(code="ai_network_error", message=f"请求失败：{e}", status_code=502)

            if resp.status_code == 200:
                resp_json = resp.json()
                items = resp_json.get("data") or []
                if not items:
                    raise ApiError(code="ai_empty_response", message="图像编辑模型未返回任何图像数据", status_code=502)

                results: list[bytes] = []
                for item in items:
                    b64 = item.get("b64_json")
                    if b64:
                        results.append(base64.b64decode(b64))
                    elif item.get("url"):
                        try:
                            img_resp = await client.get(item["url"], timeout=60.0)
                            if img_resp.status_code == 200:
                                results.append(img_resp.content)
                        except Exception as dl_err:
                            raise ApiError(code="ai_download_error", message=f"下载编辑生成图片失败：{dl_err}", status_code=502)

                if not results:
                    raise ApiError(code="ai_empty_response", message="未解析出有效图像数据", status_code=502)
                return results[:n]

            err_code, err_msg = parse_error_response(resp.status_code, resp.text)
            raise ApiError(code=err_code, message=err_msg, status_code=resp.status_code)

    async def _edit_via_chat(
        self,
        image_bytes: bytes,
        prompt: str,
        mask_bytes: bytes | None = None,
        n: int = 1,
        size: str = "1024x1024",
        extra_params: dict | None = None,
        timeout: float = 120.0,
    ) -> list[bytes]:
        """多模态 Chat 图像编辑（如 Gemini / 多模态图生图模型）。"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        user_content: list[dict[str, Any]] = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}},
        ]
        if mask_bytes:
            b64_mask = base64.b64encode(mask_bytes).decode("utf-8")
            user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_mask}"}})

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": user_content}],
            "size": size,
        }
        if extra_params:
            payload.update(extra_params)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException:
                raise ApiError(code="ai_timeout", message="图生图请求超时", status_code=504)
            except Exception as e:
                raise ApiError(code="ai_network_error", message=f"请求失败：{e}", status_code=502)

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    raise ApiError(code="ai_empty_response", message="模型未返回有效内容", status_code=502)
                message = choices[0].get("message", {})

                images_list = message.get("images") or []
                urls: list[str] = []
                for it in images_list:
                    u = it.get("image_url", {}).get("url")
                    if u:
                        urls.append(u)

                if not urls:
                    content = message.get("content", "")
                    urls = _MARKDOWN_IMAGE_RE.findall(content)

                results: list[bytes] = []
                for u in urls:
                    if u.startswith("data:image/"):
                        _, encoded = u.split(",", 1)
                        results.append(base64.b64decode(encoded))
                    elif u.startswith("http"):
                        img_resp = await client.get(u, timeout=60.0)
                        if img_resp.status_code == 200:
                            results.append(img_resp.content)

                if not results:
                    raise ApiError(code="ai_empty_response", message="Chat 图生图响应中未找到图片数据", status_code=502)
                return results[:n]

            err_code, err_msg = parse_error_response(resp.status_code, resp.text)
            raise ApiError(code=err_code, message=err_msg, status_code=resp.status_code)
