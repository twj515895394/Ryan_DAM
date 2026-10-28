from __future__ import annotations

import json
import httpx
from backend.app.services.ai.credentials import CredentialManager


def test_providers_require_token(client) -> None:
    res = client.get("/api/v1/ai/providers", headers={"Host": "127.0.0.1"})
    assert res.status_code == 401


def test_create_and_list_providers(client, headers) -> None:
    payload = {
        "name": "第三方中转 A",
        "family": "openai_compatible",
        "base_url": "https://api.thirdparty.com/v1/",
        "api_key": "sk-1234567890abcdef",
        "enabled": True,
        "settings": {"timeout": 30},
    }
    created = client.post("/api/v1/ai/providers", json=payload, headers=headers)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "第三方中转 A"
    assert body["base_url"] == "https://api.thirdparty.com/v1"  # Normalized
    assert body["has_api_key"] is True
    assert body["masked_api_key"] == "sk-****cdef"
    # Never leak raw API Key
    assert "sk-1234567890abcdef" not in str(body)

    provider_id = body["id"]

    # List
    listed = client.get("/api/v1/ai/providers", headers=headers)
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["id"] == provider_id

    # Get single
    single = client.get(f"/api/v1/ai/providers/{provider_id}", headers=headers)
    assert single.status_code == 200
    assert single.json()["name"] == "第三方中转 A"


def test_duplicate_provider_name_conflict(client, headers) -> None:
    payload = {
        "name": "本地网关",
        "family": "openai_compatible",
        "base_url": "http://127.0.0.1:8317/v1",
        "api_key": "twj123456",
    }
    assert client.post("/api/v1/ai/providers", json=payload, headers=headers).status_code == 201
    dup = client.post("/api/v1/ai/providers", json=payload, headers=headers)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "duplicate_name"


def test_update_and_delete_provider(client, headers) -> None:
    # 1. Create
    payload = {
        "name": "临时测试连接",
        "family": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-secret-initial",
    }
    created = client.post("/api/v1/ai/providers", json=payload, headers=headers).json()
    pid = created["id"]

    # 2. Update without changing api_key
    updated1 = client.patch(
        f"/api/v1/ai/providers/{pid}",
        json={"name": "重命名测试连接", "enabled": False},
        headers=headers,
    )
    assert updated1.status_code == 200
    assert updated1.json()["name"] == "重命名测试连接"
    assert updated1.json()["enabled"] is False
    assert updated1.json()["has_api_key"] is True

    # 3. Update with new api_key
    updated2 = client.patch(
        f"/api/v1/ai/providers/{pid}",
        json={"api_key": "sk-new-super-secret-1234"},
        headers=headers,
    )
    assert updated2.status_code == 200
    assert updated2.json()["masked_api_key"] == "sk-****1234"
    assert updated2.json()["credential_masked"] == "sk-****1234"

    # Verify secret is updated in CredentialManager
    # 4. Delete
    deleted = client.delete(f"/api/v1/ai/providers/{pid}", headers=headers)
    assert deleted.status_code == 204

    # Get after delete returns 404
    assert client.get(f"/api/v1/ai/providers/{pid}", headers=headers).status_code == 404


def test_create_without_key_and_then_set_key(client, headers) -> None:
    payload = {
        "name": "初始无 Key 连接",
        "family": "openai_compatible",
        "base_url": "http://127.0.0.1:8317/v1",
        "api_key": "",
    }
    created = client.post("/api/v1/ai/providers", json=payload, headers=headers).json()
    pid = created["id"]
    assert created["has_api_key"] is False
    assert created["masked_api_key"] == ""
    assert created["credential_masked"] == ""

    # 后来更新输入了 key
    updated = client.patch(
        f"/api/v1/ai/providers/{pid}",
        json={"api_key": "sk-late-added-key-8888"},
        headers=headers,
    ).json()
    assert updated["has_api_key"] is True
    assert updated["masked_api_key"] == "sk-****8888"
    assert updated["credential_masked"] == "sk-****8888"


def test_test_provider_endpoint(client, headers, monkeypatch) -> None:
    # Create provider
    payload = {
        "name": "端点测试 Provider",
        "family": "openai_compatible",
        "base_url": "https://mock.api.com/v1",
        "api_key": "sk-mock-key-1234",
    }
    created = client.post("/api/v1/ai/providers", json=payload, headers=headers).json()
    pid = created["id"]

    # Mock httpx.Client calls inside test_provider_connection
    def mock_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/chat/completions" in path:
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        if "/images/generations" in path:
            return httpx.Response(200, json={"data": [{"url": "https://img.test.com/1.png"}]})
        return httpx.Response(404, text="Not supported")

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))

    from backend.app.services.ai import provider_service
    original_test = provider_service.test_provider_connection

    def wrapped_test(*args, **kwargs):
        kwargs["client"] = mock_client
        return original_test(*args, **kwargs)

    monkeypatch.setattr(provider_service, "test_provider_connection", wrapped_test)

    test_res = client.post(
        f"/api/v1/ai/providers/{pid}/test",
        json={
            "model_mapping": {
                "text_optimize": "gpt-4o-mini",
                "image_generate": "gpt-image-2.5",
            }
        },
        headers=headers,
    )
    assert test_res.status_code == 200
    data = test_res.json()
    assert data["success"] is True
    assert "text_optimize" in data["results"]
    assert data["results"]["text_optimize"]["supported"] is True
    assert data["results"]["image_generate"]["supported"] is True


def test_fetch_remote_models_openai_format(client, headers, monkeypatch) -> None:
    # 1. 创建 OpenAI Compatible Provider
    payload = {
        "name": "OpenAI 远程模型测试 Provider",
        "family": "openai_compatible",
        "base_url": "http://127.0.0.1:8317/v1",
        "api_key": "sk-mock-key-openai",
    }
    created = client.post("/api/v1/ai/providers", json=payload, headers=headers).json()
    pid = created["id"]

    # 2. Mock GET /v1/models
    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert "/models" in request.url.path
        assert request.headers.get("authorization") == "Bearer sk-mock-key-openai"
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"id": "gpt-4o", "name": "GPT-4o 旗舰模型", "owned_by": "openai"},
                    {"id": "dall-e-3", "name": "DALL-E 3 高清生图", "owned_by": "system"},
                    {"id": "gpt-4o-mini", "owned_by": "openai"},
                ],
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))

    from backend.app.services.ai import provider_service

    original_fetch = provider_service.fetch_remote_models

    def wrapped_fetch(*args, **kwargs):
        kwargs["client"] = mock_client
        return original_fetch(*args, **kwargs)

    monkeypatch.setattr(provider_service, "fetch_remote_models", wrapped_fetch)

    # 3. 发送请求测试
    res = client.get(f"/api/v1/ai/providers/{pid}/remote-models", headers=headers)
    assert res.status_code == 200
    models = res.json()
    assert len(models) == 3
    # 验证按 id 排序与字段映射
    ids = [m["id"] for m in models]
    assert ids == ["dall-e-3", "gpt-4o", "gpt-4o-mini"]
    dalle = next(m for m in models if m["id"] == "dall-e-3")
    assert dalle["name"] == "DALL-E 3 高清生图"
    assert dalle["description"] == "system"


def test_fetch_remote_models_gemini_format(client, headers, monkeypatch) -> None:
    # 1. 创建 Gemini Native Provider
    payload = {
        "name": "Gemini 远程模型测试 Provider",
        "family": "gemini_native",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": "ai-gemini-key-xyz",
    }
    created = client.post("/api/v1/ai/providers", json=payload, headers=headers).json()
    pid = created["id"]

    # 2. Mock GET /v1beta/models?key=...
    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert "/models" in request.url.path
        assert request.headers.get("x-goog-api-key") == "ai-gemini-key-xyz"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-1.5-pro",
                        "displayName": "Gemini 1.5 Pro",
                        "description": "General multimodal reasoning model",
                    },
                    {
                        "name": "models/imagen-3.0-generate-002",
                        "displayName": "Imagen 3 图像生成",
                        "description": "Google native image generation",
                    },
                ]
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))

    from backend.app.services.ai import provider_service

    original_fetch = provider_service.fetch_remote_models

    def wrapped_fetch(*args, **kwargs):
        kwargs["client"] = mock_client
        return original_fetch(*args, **kwargs)

    monkeypatch.setattr(provider_service, "fetch_remote_models", wrapped_fetch)

    # 3. 发送请求测试
    res = client.get(f"/api/v1/ai/providers/{pid}/remote-models", headers=headers)
    assert res.status_code == 200
    models = res.json()
    assert len(models) == 2
    # 验证 "models/" 前缀已被剥离
    assert models[0]["id"] == "gemini-1.5-pro"
    assert models[0]["name"] == "Gemini 1.5 Pro"
    assert models[1]["id"] == "imagen-3.0-generate-002"
    assert models[1]["name"] == "Imagen 3 图像生成"


def test_fetch_remote_models_error_cases(client, headers, monkeypatch) -> None:
    # 1. 不存在的 provider_id 返回 404
    not_found = client.get("/api/v1/ai/providers/99999/remote-models", headers=headers)
    assert not_found.status_code == 404

    # 2. Provider 请求远端报错 502/401 等
    payload = {
        "name": "错误测试 Provider",
        "family": "openai_compatible",
        "base_url": "http://127.0.0.1:8317/v1",
        "api_key": "sk-err-key",
    }
    pid = client.post("/api/v1/ai/providers", json=payload, headers=headers).json()["id"]

    def mock_err_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API Key"}})

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_err_handler))

    from backend.app.services.ai import provider_service

    original_fetch = provider_service.fetch_remote_models

    def wrapped_fetch(*args, **kwargs):
        kwargs["client"] = mock_client
        return original_fetch(*args, **kwargs)

    monkeypatch.setattr(provider_service, "fetch_remote_models", wrapped_fetch)

    err_res = client.get(f"/api/v1/ai/providers/{pid}/remote-models", headers=headers)
    assert err_res.status_code == 400
    assert err_res.json()["error"]["code"] == "remote_models_failed"


def test_fetch_remote_models_auto_heal_v1_and_dynamic_test(client, headers, monkeypatch) -> None:
    # 测试未加 /v1 的 base_url 能够自动发现 /v1/models 并在能力测试时动态探测模型
    payload = {
        "name": "未加 v1 的网关 Provider",
        "family": "openai_compatible",
        "base_url": "http://127.0.0.1:8317",
        "api_key": "twj123456",
    }
    pid = client.post("/api/v1/ai/providers", json=payload, headers=headers).json()["id"]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        # 模拟没有 /v1 的 /models 返回 404，而 /v1/models 返回 200
        if url_str == "http://127.0.0.1:8317/models":
            return httpx.Response(404, text="Not Found")
        if url_str == "http://127.0.0.1:8317/v1/models":
            return httpx.Response(200, json={
                "data": [
                    {"id": "gemini-3.8-flash-low"},
                    {"id": "gpt-image-2.5"}
                ]
            })
        if "/chat/completions" in url_str:
            # 仅当使用 gemini-3.8-flash-low 时通过，硬编码 gpt-4o-mini 则返回 400
            req_data = json.loads(request.read())
            if req_data.get("model") == "gemini-3.8-flash-low":
                return httpx.Response(200, json={"choices": [{"message": {"content": "pong"}}]})
            return httpx.Response(400, json={"error": {"message": "model_not_found"}})
        if "/images/generations" in url_str:
            return httpx.Response(200, json={"data": [{"b64_json": "fake_b64"}]})
        return httpx.Response(404, text="Not Found")

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))

    from backend.app.services.ai import provider_service
    original_fetch = provider_service.fetch_remote_models
    original_test = provider_service.test_provider_connection

    def wrapped_fetch(*args, **kwargs):
        kwargs["client"] = mock_client
        return original_fetch(*args, **kwargs)

    def wrapped_test(*args, **kwargs):
        kwargs["client"] = mock_client
        return original_test(*args, **kwargs)

    monkeypatch.setattr(provider_service, "fetch_remote_models", wrapped_fetch)
    monkeypatch.setattr(provider_service, "test_provider_connection", wrapped_test)

    # 1. 验证获取远程模型时自愈补齐 /v1
    models_res = client.get(f"/api/v1/ai/providers/{pid}/remote-models", headers=headers)
    assert models_res.status_code == 200
    models_data = models_res.json()
    assert len(models_data) == 2

    # 验证 base_url 已自愈为 /v1
    provider_info = client.get(f"/api/v1/ai/providers/{pid}", headers=headers).json()
    assert provider_info["base_url"] == "http://127.0.0.1:8317/v1"

    # 2. 验证空 payload 测试时，动态选取 gemini-3.8-flash-low 与 gpt-image-2.5 成功通过测试
    test_res = client.post(f"/api/v1/ai/providers/{pid}/test", json={}, headers=headers)
    assert test_res.status_code == 200
    test_data = test_res.json()
    assert test_data["success"] is True
    assert test_data["results"]["text_optimize"]["supported"] is True
    assert test_data["results"]["text_optimize"]["model_id"] == "gemini-3.8-flash-low"
    assert test_data["results"]["image_generate"]["supported"] is True
    assert test_data["results"]["image_generate"]["model_id"] == "gpt-image-2.5"

