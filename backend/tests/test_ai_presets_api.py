from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.models.ai.model_config import AiDefaultBinding, AiModelProfile
from backend.app.models.ai.provider import AiProviderInstance
from backend.app.models.ai.template import AiCreationPreset
from backend.app.services.ai.credentials import CredentialManager
from backend.app.services.ai.preset_service import ensure_builtin_presets


def test_presets_crud_api(client: TestClient, headers: dict[str, str], app: FastAPI) -> None:
    # 1. 列表查询，自动注入内置预设
    list_resp = client.get("/api/v1/ai/presets", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 4
    codes = [item["code"] for item in items]
    assert "photorealistic" in codes
    assert "anime_art" in codes

    # 2. 新增自定义预设 POST /api/v1/ai/presets
    create_payload = {
        "name": "Custom SciFi Oil Painting",
        "code": "custom_scifi_oil",
        "description": "古典厚涂油画质感的科幻场景",
        "creation_mode": "image_generate",
        "system_rules": "强调厚涂油画笔触、质感画布纹理、古典大师级光影与宏大科幻构图对撞。",
        "default_params": {"prompt_suffix": ", oil on canvas, textured paint strokes, masterwork"},
        "sort_order": 10,
    }
    create_resp = client.post("/api/v1/ai/presets", json=create_payload, headers=headers)
    assert create_resp.status_code == 201
    preset_data = create_resp.json()
    preset_id = preset_data["id"]
    assert preset_data["name"] == "Custom SciFi Oil Painting"
    assert preset_data["is_builtin"] is False

    # 3. 获取单个预设 GET /api/v1/ai/presets/{id}
    detail_resp = client.get(f"/api/v1/ai/presets/{preset_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == preset_id

    # 4. 更新预设 PUT /api/v1/ai/presets/{id}
    update_payload = {"name": "Custom SciFi Oil Painting v2"}
    update_resp = client.put(f"/api/v1/ai/presets/{preset_id}", json=update_payload, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Custom SciFi Oil Painting v2"

    # 5. 删除内置预设被拦截 DELETE /api/v1/ai/presets/{builtin_id}
    builtin = next(item for item in items if item["is_builtin"])
    del_builtin_resp = client.delete(f"/api/v1/ai/presets/{builtin['id']}", headers=headers)
    assert del_builtin_resp.status_code == 400

    # 6. 删除自定义预设成功
    del_custom_resp = client.delete(f"/api/v1/ai/presets/{preset_id}", headers=headers)
    assert del_custom_resp.status_code == 204


@pytest.mark.anyio
async def test_prompt_optimize_endpoint(client: TestClient, headers: dict[str, str], app: FastAPI) -> None:
    session_factory = app.state.session_factory
    with session_factory() as db:
        prov = AiProviderInstance(
            family="openai_compatible",
            name="Chat Opt Provider",
            base_url="https://api.example.com/v1",
            credential_ref="opt_cred_key",
            enabled=True,
        )
        db.add(prov)
        db.commit()
        db.refresh(prov)

        CredentialManager.save_credential("sk-chat-secret", ref_id=prov.credential_ref)

        model = AiModelProfile(
            provider_id=prov.id,
            model_id="gpt-4o-mini",
            name="GPT-4o Mini Chat",
            adapter_kind="openai_standard",
            capabilities_json='{"text_optimize": true}',
            enabled=True,
        )
        db.add(model)
        db.commit()
        db.refresh(model)

        binding = AiDefaultBinding(
            capability="text_optimize",
            scene="prompt_optimize",
            model_profile_id=model.id,
        )
        db.add(binding)
        db.commit()

        # 确保内置预设已初始化
        ensure_builtin_presets(db)
        preset = db.query(AiCreationPreset).filter(AiCreationPreset.code == "photorealistic").first()
        preset_id = preset.id if preset else None

    with patch(
        "backend.app.services.ai.adapters.openai_compatible.OpenAICompatibleAdapter.chat_complete",
        new_callable=AsyncMock,
    ) as mock_chat:
        mock_chat.return_value = (
            "A serene Japanese tea room at sunrise, soft golden dust motes floating in morning light, "
            "wooden tatami textures, steaming ceramic teapot, wide angle depth of field"
        )

        opt_payload = {
            "prompt": "tea room at morning",
            "preset_id": preset_id,
            "custom_instruction": "emphasize morning light",
        }

        resp = client.post("/api/v1/ai/prompt/optimize", json=opt_payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["original_prompt"] == "tea room at morning"
        assert "A serene Japanese tea room" in data["optimized_prompt"]
        # 验证预设的 prompt_suffix 自动融入
        assert "masterpiece" in data["optimized_prompt"]
        assert data["model_profile_id"] == model.id
        assert data["provider_name"] == "Chat Opt Provider"
