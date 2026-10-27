from __future__ import annotations


def test_models_and_defaults_flow(client, headers) -> None:
    # 1. Create a Provider first
    p_res = client.post(
        "/api/v1/ai/providers",
        json={
            "name": "本地兼容网关",
            "family": "openai_compatible",
            "base_url": "http://127.0.0.1:8317/v1",
            "api_key": "twj-test-key",
        },
        headers=headers,
    )
    assert p_res.status_code == 201
    provider_id = p_res.json()["id"]

    # 2. Add ModelProfile 1 (Text & Vision)
    m1_res = client.post(
        f"/api/v1/ai/providers/{provider_id}/models",
        json={
            "model_id": "gpt-4o-mini",
            "name": "GPT-4o mini (快速文本/视觉)",
            "adapter_kind": "openai_standard",
            "enabled": True,
            "capabilities": {
                "text_optimize": {"supported": True},
                "image_understand": {"supported": True, "max_reference_count": 5},
                "image_generate": {"supported": False},
            },
        },
        headers=headers,
    )
    assert m1_res.status_code == 201
    m1 = m1_res.json()
    assert m1["model_id"] == "gpt-4o-mini"
    assert m1["capabilities"]["image_understand"]["supported"] is True

    # 3. Add ModelProfile 2 (Image Generation)
    m2_res = client.post(
        f"/api/v1/ai/providers/{provider_id}/models",
        json={
            "model_id": "dall-e-3",
            "name": "DALL-E 3 (生图)",
            "adapter_kind": "openai_standard",
            "enabled": True,
            "capabilities": {
                "image_generate": {
                    "supported": True,
                    "supported_aspect_ratios": ["1:1", "16:9", "9:16"],
                    "supported_sizes": ["1024x1024", "1792x1024", "1024x1792"],
                }
            },
        },
        headers=headers,
    )
    assert m2_res.status_code == 201
    m2 = m2_res.json()

    # 4. Duplicate model_id under same provider rejected
    dup_res = client.post(
        f"/api/v1/ai/providers/{provider_id}/models",
        json={
            "model_id": "gpt-4o-mini",
            "name": "重复模型",
        },
        headers=headers,
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "duplicate_model"

    # 5. List models
    list_res = client.get(f"/api/v1/ai/providers/{provider_id}/models", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 2

    # 6. Set Default Binding
    # 6a. Try to set m1 as image_generate default -> Expect rejection because capability not supported
    err_bind = client.post(
        "/api/v1/ai/defaults",
        json={
            "capability": "image_generate",
            "scene": "global",
            "model_profile_id": m1["id"],
        },
        headers=headers,
    )
    assert err_bind.status_code == 400
    assert err_bind.json()["error"]["code"] == "capability_unsupported"

    # 6b. Set m1 as text_optimize default
    b1_res = client.post(
        "/api/v1/ai/defaults",
        json={
            "capability": "text_optimize",
            "scene": "global",
            "model_profile_id": m1["id"],
        },
        headers=headers,
    )
    assert b1_res.status_code == 200
    assert b1_res.json()["capability"] == "text_optimize"
    assert b1_res.json()["model_id"] == "gpt-4o-mini"

    # 6c. Set m2 as image_generate default
    b2_res = client.post(
        "/api/v1/ai/defaults",
        json={
            "capability": "image_generate",
            "scene": "global",
            "model_profile_id": m2["id"],
        },
        headers=headers,
    )
    assert b2_res.status_code == 200
    assert b2_res.json()["model_id"] == "dall-e-3"

    # 7. List Defaults
    defaults_list = client.get("/api/v1/ai/defaults", headers=headers)
    assert defaults_list.status_code == 200
    caps = {item["capability"]: item["model_id"] for item in defaults_list.json()}
    assert caps["text_optimize"] == "gpt-4o-mini"
    assert caps["image_generate"] == "dall-e-3"

    # 8. Test Resolution Service in python
    from backend.app.api.v1.deps import get_db
    from backend.app.services.ai.model_service import resolve_model_for_capability

    # Using test db session
    from backend.app.db.session import create_sqlite_engine, create_session_factory
    from backend.app.models.ai.model_config import AiModelProfile

    # Update profile
    patch_res = client.patch(
        f"/api/v1/ai/models/{m1['id']}",
        json={"name": "GPT-4o mini 改名版"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "GPT-4o mini 改名版"
