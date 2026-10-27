from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.models.ai.provider import AiProviderInstance
from backend.app.models.ai.model_config import AiModelProfile, AiDefaultBinding
from backend.app.models.ai.task import AiTask, AiResult
from backend.app.services.ai.credentials import CredentialManager


def _make_png_bytes(width: int = 256, height: int = 256, color: str = "green") -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.anyio
async def test_submit_image_generation_e2e(client: TestClient, headers: dict[str, str], app: FastAPI) -> None:
    session_factory = app.state.session_factory
    with session_factory() as db:
        # 1. 创建 Provider 并注入密钥
        prov = AiProviderInstance(
            family="openai_compatible",
            name="Gen Provider",
            base_url="https://api.example.com/v1",
            credential_ref="gen_cred_key",
            enabled=True,
        )
        db.add(prov)
        db.commit()
        db.refresh(prov)
        prov_id = prov.id

        CredentialManager.save_credential("sk-test-secret-123", ref_id=prov.credential_ref)

        # 2. 创建生图模型
        model = AiModelProfile(
            provider_id=prov.id,
            model_id="dall-e-3",
            name="DALL-E 3 Test",
            adapter_kind="openai_standard",
            capabilities_json='{"image_generate": true}',
            enabled=True,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        model_id = model.id

        # 3. 设置默认生图绑定
        binding = AiDefaultBinding(
            capability="image_generate",
            scene="general",
            model_profile_id=model.id,
        )
        db.add(binding)
        db.commit()

    fake_png = _make_png_bytes(512, 512, "blue")

    # 4. Mock OpenAICompatibleAdapter.generate_images 并提交生成任务
    with patch(
        "backend.app.services.ai.adapters.openai_compatible.OpenAICompatibleAdapter.generate_images",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = [fake_png]

        payload = {
            "prompt": "Futuristic neon city with flying cars",
            "model_profile_id": model_id,
            "params": {"size": "512x512", "n": 1},
        }

        resp = client.post("/api/v1/ai/tasks", json=payload, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        task_id = data["id"]
        assert task_id.startswith("aitask_")
        assert data["status"] in ("queued", "running", "succeeded")

        # 等待后台执行完成
        import asyncio
        for _ in range(50):
            t_resp = client.get(f"/api/v1/ai/tasks/{task_id}", headers=headers)
            t_data = t_resp.json()
            if t_data["status"] in ("succeeded", "failed", "canceled"):
                break
            await asyncio.sleep(0.05)

        assert t_data["status"] == "succeeded"
        assert t_data["progress_pct"] == 100
        assert len(t_data["results"]) == 1

        result_item = t_data["results"][0]
        assert result_item["width"] == 512
        assert result_item["height"] == 512
        assert Path(result_item["history_file_path"]).exists()

        # 验证历史结果接口能查询到
        res_resp = client.get(f"/api/v1/ai/results/{result_item['id']}", headers=headers)
        assert res_resp.status_code == 200
        assert res_resp.json()["id"] == result_item["id"]
