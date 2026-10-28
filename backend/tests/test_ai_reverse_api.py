from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.app.models.asset import Asset
from backend.app.models.ai.provider import AiProviderInstance
from backend.app.models.ai.model_config import AiModelProfile, AiDefaultBinding
from backend.app.models.ai.template import AiReverseTemplate


def test_reverse_templates_crud(client: TestClient, headers) -> None:
    # 1. 查询模板列表，应自动创建 3 个内置模板
    resp = client.get("/api/v1/ai/reverse/templates", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 3
    codes = {item["code"] for item in items if item["code"]}
    assert {"general_description", "character_features", "artistic_style"} <= codes

    # 2. 创建自定义模板
    create_payload = {
        "name": "电商产品精修反推",
        "code": "ecommerce_product",
        "description": "侧重主体商品材质、包装、灯光阴影与白底/场景质感",
        "system_prompt": "你是一个电商视觉分析专家，请精准解析输入商品图的材质与光影细节。",
        "user_prompt_template": "输出商业级产品摄影提示词：",
        "enabled": True,
        "sort_order": 10,
    }
    create_resp = client.post("/api/v1/ai/reverse/templates", json=create_payload, headers=headers)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "电商产品精修反推"
    assert created["is_builtin"] is False
    tpl_id = created["id"]

    # 3. 更新模板
    update_resp = client.put(
        f"/api/v1/ai/reverse/templates/{tpl_id}",
        json={"name": "电商产品精修反推 V2", "sort_order": 20},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "电商产品精修反推 V2"

    # 4. 删除自定义模板
    del_resp = client.delete(f"/api/v1/ai/reverse/templates/{tpl_id}", headers=headers)
    assert del_resp.status_code == 204

    # 5. 尝试删除内置模板应被拒绝
    builtin_tpl = next(item for item in items if item["is_builtin"])
    del_builtin_resp = client.delete(f"/api/v1/ai/reverse/templates/{builtin_tpl['id']}", headers=headers)
    assert del_builtin_resp.status_code == 400
    assert del_builtin_resp.json()["error"]["code"] == "cannot_delete_builtin"

    # 6. 内置反推模板支持修改与一键恢复默认 (Reset)
    orig_tpl_name = builtin_tpl["name"]
    put_builtin_resp = client.put(
        f"/api/v1/ai/reverse/templates/{builtin_tpl['id']}",
        json={"name": f"{orig_tpl_name} (定制版)", "system_prompt": "修改后的系统反推提示词"},
        headers=headers,
    )
    assert put_builtin_resp.status_code == 200
    assert put_builtin_resp.json()["name"] == f"{orig_tpl_name} (定制版)"

    reset_resp = client.post(f"/api/v1/ai/reverse/templates/{builtin_tpl['id']}/reset", headers=headers)
    assert reset_resp.status_code == 200
    assert reset_resp.json()["name"] == orig_tpl_name


@pytest.mark.anyio
async def test_single_image_reverse_mock(client: TestClient, app, headers, tmp_path) -> None:
    # 准备测试图片文件
    img_file = tmp_path / "test_photo.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"0" * 100)

    # 获取 session 并插入测试数据
    session_factory = app.state.session_factory
    with session_factory() as session:
        asset = Asset(
            name="test_photo.jpg",
            extension="jpg",
            asset_type="image",
            size_bytes=107,
            source_type="managed",
            file_path=str(img_file),
            status="active",
            thumbnail_status="ready",
            prompt_text="旧的手动提示词",
            prompt_origin="manual",
            prompt_revision=1,
        )
        session.add(asset)

        provider = AiProviderInstance(
            family="openai_compatible",
            name="Test Vision Provider",
            base_url="https://api.testvision.com/v1",
            credential_ref="cred_test_123",
            enabled=True,
        )
        session.add(provider)
        session.flush()

        profile = AiModelProfile(
            provider_id=provider.id,
            model_id="gpt-4o-mini",
            name="GPT-4o Mini Vision",
            adapter_kind="openai_standard",
            capabilities_json='{"image_understand": {"supported": true}, "image_generate": {"supported": false}}',
            enabled=True,
        )
        session.add(profile)
        session.flush()

        binding = AiDefaultBinding(
            capability="image_understand",
            scene="global",
            model_profile_id=profile.id,
        )
        session.add(binding)
        session.commit()
        asset_id = asset.id

    # Mock OpenAICompatibleAdapter.understand_image
    mock_reversed_text = "masterpiece, 1girl, detailed eyes, cinematic lighting, photorealistic"
    with patch(
        "backend.app.services.ai.adapters.openai_compatible.OpenAICompatibleAdapter.understand_image",
        new_callable=AsyncMock,
        return_value=mock_reversed_text,
    ):
        resp = client.post(
            f"/api/v1/ai/reverse/assets/{asset_id}",
            json={},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_id"] == asset_id
        assert data["reversed_prompt"] == mock_reversed_text
        assert data["has_conflict"] is True
        assert data["current_asset_prompt"] == "旧的手动提示词"
        assert data["current_asset_revision"] == 1
        assert data["model_id"] == "gpt-4o-mini"

        # 测试语言参数传递 (中文默认 vs 英文)
        with patch(
            "backend.app.services.ai.adapters.openai_compatible.OpenAICompatibleAdapter.understand_image",
            new_callable=AsyncMock,
            return_value="中文高清画面描述",
        ) as mock_understand:
            resp_zh = client.post(
                f"/api/v1/ai/reverse/assets/{asset_id}",
                json={"language": "zh"},
                headers=headers,
            )
            assert resp_zh.status_code == 200
            _, kwargs = mock_understand.call_args
            assert "语言要求" in kwargs["system_prompt"]

        with patch(
            "backend.app.services.ai.adapters.openai_compatible.OpenAICompatibleAdapter.understand_image",
            new_callable=AsyncMock,
            return_value="English prompt details",
        ) as mock_understand_en:
            resp_en = client.post(
                f"/api/v1/ai/reverse/assets/{asset_id}",
                json={"language": "en"},
                headers=headers,
            )
            assert resp_en.status_code == 200
            _, kwargs = mock_understand_en.call_args
            assert "Language Requirement" in kwargs["system_prompt"]

