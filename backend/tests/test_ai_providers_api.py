from __future__ import annotations

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

    # Verify secret is updated in CredentialManager
    # 4. Delete
    deleted = client.delete(f"/api/v1/ai/providers/{pid}", headers=headers)
    assert deleted.status_code == 204

    # Get after delete returns 404
    assert client.get(f"/api/v1/ai/providers/{pid}", headers=headers).status_code == 404


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
