# OpenAI Compatible 第三方图片与文本 API 协议差异及适配规范（V2-02）

- **核实日期**：2026-10-27
- **关联任务**：`IMPLEMENTATION_PLAN_V2.md` 之 `V2-02 第三方图片/文本 API 协议 PoC`
- **验证代码**：`backend/app/services/ai/protocol_poc.py` / `backend/tests/test_ai_protocol_poc.py`

---

## 1. 核心结论与协议背景

在实际的第三方中转和代理服务中，“OpenAI 兼容（OpenAI Compatible）”往往只保证了 `/v1/chat/completions` 文本端点的兼容性。在多模态视觉、文生图和图生图/编辑场景下，存在以下显著协议差异：

| 能力类型 | 官方标准 OpenAI 路由 | 常见第三方 / 本地中转（如 8045/8317）差异 | 适配与处理策略 |
|---|---|---|---|
| **文本优化 (`text_optimize`)** | `POST /chat/completions`<br>JSON 文本 | 高度统一，标准 messages (`system` + `user`) | 统一使用标准 Chat Completions，温度设置为 0.2~0.7 |
| **视觉反推 (`image_understand`)** | `POST /chat/completions`<br>多模态 `image_url` | 大部分支持 `data:image/png;base64,...` URL；部分仅支持公网 http 链接；纯文本模型返回 400 | 本地图片统一转为 base64 data URL 提交；若返回 400 vision 错误归类为 `capability_unsupported` |
| **图片生成 (`image_generate`)** | `POST /images/generations`<br>`model`, `prompt`, `n`, `size` | **主要差异分歧点**：<br>1. GPT 图像模型：标准 `/images/generations` 返回 `data[].url` 或 `data[].b64_json`；<br>2. Gemini 图像模型：多数中转服务走 `POST /chat/completions`，在 `content` 中返回 Markdown `![alt](data:image/...)` 或在 `message.images` 返回列表；<br>3. 很多纯文本中转对 `/images/generations` 直接返回 404/405 | **双重探测与路由**：<br>- 默认走 `/images/generations`；<br>- 若模型为 `gemini` 系列或配置指定为 Chat 路由，则走 `chat/completions`；<br>- 解析器同时兼容提取 `data[].url`, `data[].b64_json`, `message.images` 和 Markdown 正则图片 |
| **图片编辑 (`image_edit`)** | `POST /images/edits`<br>`multipart/form-data` | 绝大多数第三方中转**不支持**标准编辑端点 (404/405)；部分仅支持单张，部分支持 `image[]` 多图 | 严格限制为已明确支持编辑的模型；探针显式测试 `/images/edits`，不支持时标红禁用，避免用户误提交 |

---

## 2. 响应数据提取规范（多格式兼容解析）

```python
def extract_images_from_payload(data: dict) -> list[str]:
    # 1. 优先提取 OpenAI Images 标准格式
    if "data" in data and isinstance(data["data"], list):
        return [item.get("url") or item.get("b64_json") for item in data["data"] if item]

    # 2. 提取 Chat Completions 扩展格式
    if "choices" in data and data["choices"]:
        msg = data["choices"][0].get("message", {})
        # 2a: message.images 结构（OpenRouter 等风格）
        if "images" in msg and msg["images"]:
            return [it.get("image_url", {}).get("url") for it in msg["images"] if it]
        # 2b: Markdown 内嵌 base64 / URL（本地网关风格）
        content = msg.get("content", "")
        return MARKDOWN_IMAGE_RE.findall(content)

    return []
```

---

## 3. 错误归一化契约（Unified Error Classification）

所有第三方 API 异常在系统内部归一化为确定性的错误码：

| HTTP 状态码 / 特征 | 归一化错误码 | 业务含义与 UI 反馈 |
|---|---|---|
| 401, 403 | `unauthorized` | API Key 无效或缺少访问权限 |
| 404 (含 model 关键字) | `model_not_found` | 模型在所选 Provider 下不存在 |
| 404 / 405 / 501 (端点不支持) | `capability_unsupported` | 当前 Provider 不支持该能力接口（例如不支持生图或编辑） |
| 429 | `rate_limit` | 上游限流或配额已耗尽 |
| 422 | `invalid_parameter` | 尺寸/比例/参考图数等参数校验不兼容 |
| Timeout | `timeout` | 网络连接超时，提示检查 Base URL |
| 5xx | `server_error` | 服务提供商服务故障 |

---

## 4. 后续任务落地指导

- **V2-03 (Provider 连接管理)**：在测试连接时，不可仅凭 `/models` 200 就判定全部能力可用，必须调用 `probe_all_capabilities` 针对各能力模型独立展示测试状态。
- **V2-04 (模型与能力 Schema)**：为不同模型分别指定适配器（`openai_images` vs `chat_multimodal_images`），从而在生成时选择正确的路由。
- **V2-09 (生图闭环)**：复用上述兼容图片提取逻辑，将拿到的 URL 或 base64 安全复制并落盘至本地永久历史目录。
