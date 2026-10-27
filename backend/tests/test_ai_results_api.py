from __future__ import annotations

import io
from pathlib import Path
import pytest
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError
from backend.app.models.ai.provider import AiProviderInstance
from backend.app.models.ai.model_config import AiModelProfile
from backend.app.models.ai.task import AiTask, AiResult
from backend.app.services.ai.storage_service import (
    commit_generated_result,
    delete_history_result,
    get_ai_history_layout,
    save_input_snapshot,
)
from backend.app.services.settings_service import get_managed_root


def _create_dummy_image(path: Path, width: int = 100, height: int = 100, color: str = "red") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color=color)
    img.save(path, format="PNG")


def test_save_input_snapshot(app: FastAPI, tmp_path: Path) -> None:
    session_factory = app.state.session_factory
    with session_factory() as db:
        managed_root = get_managed_root(db)
        task = AiTask(id="task_snap_test", task_type="image_generate", status="running")
        db.add(task)
        db.commit()

        # 1. 正常快照
        src = tmp_path / "original_ref.png"
        _create_dummy_image(src, width=200, height=150)

        ref = save_input_snapshot(
            db=db,
            task_id=task.id,
            seq=0,
            source_path=src,
            role="character",
            source_kind="local_upload",
        )
        assert ref.task_id == task.id
        assert ref.seq == 0
        assert ref.role == "character"
        assert Path(ref.snapshot_path).exists()
        assert ref.sha256 is not None

        # 2. 0 字节文件被拦截
        empty_file = tmp_path / "empty.png"
        empty_file.write_bytes(b"")
        with pytest.raises(ApiError) as exc_info:
            save_input_snapshot(
                db=db,
                task_id=task.id,
                seq=1,
                source_path=empty_file,
            )
        assert exc_info.value.code == "invalid_input_file"


def test_commit_generated_result_validation(app: FastAPI, tmp_path: Path) -> None:
    session_factory = app.state.session_factory
    with session_factory() as db:
        managed_root = get_managed_root(db)
        task = AiTask(id="task_commit_test", task_type="image_generate", status="running")
        db.add(task)
        db.commit()

        # 1. 0 字节损坏文件拦截
        zero_file = tmp_path / "zero.png"
        zero_file.write_bytes(b"")
        with pytest.raises(ApiError) as exc_info:
            commit_generated_result(db=db, task_id=task.id, idx=0, staging_file=zero_file)
        assert exc_info.value.code == "corrupted_result"

        # 2. 非合法图片截断文件拦截
        corrupt_file = tmp_path / "corrupt.png"
        corrupt_file.write_bytes(b"NOT_A_VALID_PNG_HEADER_RANDOM_BYTES")
        with pytest.raises(ApiError) as exc_info:
            commit_generated_result(db=db, task_id=task.id, idx=0, staging_file=corrupt_file)
        assert exc_info.value.code == "corrupted_result"

        # 3. 正常生成结果落盘
        valid_staging = tmp_path / "valid.png"
        _create_dummy_image(valid_staging, width=512, height=512, color="blue")

        result = commit_generated_result(
            db=db,
            task_id=task.id,
            idx=0,
            staging_file=valid_staging,
            mime_type="image/png",
        )
        assert result.task_id == task.id
        assert result.width == 512
        assert result.height == 512
        assert result.size_bytes > 0
        assert Path(result.history_file_path).exists()
        # 原暂存文件已被原子移走
        assert not valid_staging.exists()


def test_ai_results_api_flow(client: TestClient, headers: dict[str, str], app: FastAPI, tmp_path: Path) -> None:
    session_factory = app.state.session_factory
    with session_factory() as db:
        prov = AiProviderInstance(
            family="openai_compatible",
            name="Results Test Provider",
            base_url="https://api.example.com/v1",
            credential_ref="test_cred_res",
            enabled=True,
        )
        db.add(prov)
        db.commit()
        db.refresh(prov)

        model = AiModelProfile(
            provider_id=prov.id,
            model_id="res-gen-model",
            name="Results Model",
            adapter_kind="openai_standard",
            capabilities_json='{"image_generate": true}',
            enabled=True,
        )
        db.add(model)
        db.commit()
        db.refresh(model)

        task = AiTask(
            id="task_res_flow",
            task_type="image_generate",
            provider_id=prov.id,
            model_profile_id=model.id,
            status="succeeded",
            prompt_final="Sunset over neon mountains",
        )
        db.add(task)
        db.commit()

        # 生成并落盘结果
        staging = tmp_path / "res_out.png"
        _create_dummy_image(staging, width=640, height=480, color="purple")
        res_record = commit_generated_result(db=db, task_id=task.id, idx=0, staging_file=staging)
        result_id = res_record.id

    # 1. 列表查询 GET /api/v1/ai/results
    list_resp = client.get("/api/v1/ai/results", headers=headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 1
    hit = next((item for item in data["items"] if item["id"] == result_id), None)
    assert hit is not None
    assert hit["width"] == 640
    assert hit["height"] == 480
    assert hit["task"]["prompt_final"] == "Sunset over neon mountains"

    # 2. 详情查询 GET /api/v1/ai/results/{id}
    detail_resp = client.get(f"/api/v1/ai/results/{result_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == result_id

    # 3. 文件流 GET /api/v1/ai/results/{id}/content
    content_resp = client.get(f"/api/v1/ai/results/{result_id}/content", headers=headers)
    assert content_resp.status_code == 200
    assert content_resp.headers["content-type"] == "image/png"
    assert len(content_resp.content) > 0

    # 4. 删除无 confirm 拒绝 DELETE /api/v1/ai/results/{id}
    del_unconfirmed = client.delete(f"/api/v1/ai/results/{result_id}", headers=headers)
    assert del_unconfirmed.status_code == 400
    assert del_unconfirmed.json()["error"]["code"] == "confirmation_required"

    # 5. 确认删除 DELETE /api/v1/ai/results/{id}?confirm=true
    del_confirmed = client.delete(f"/api/v1/ai/results/{result_id}?confirm=true", headers=headers)
    assert del_confirmed.status_code == 200
    assert del_confirmed.json()["status"] == "deleted"

    # 再次查询列表应已被排除
    list_after = client.get("/api/v1/ai/results", headers=headers).json()
    assert not any(item["id"] == result_id for item in list_after["items"])


def test_import_result_to_asset_and_batch_api(client: TestClient, headers: dict[str, str], app: FastAPI, tmp_path: Path) -> None:
    session_factory = app.state.session_factory
    with session_factory() as db:
        prov = AiProviderInstance(
            family="openai_compatible",
            name="Import Test Provider",
            base_url="https://api.example.com/v1",
            credential_ref="test_cred_import",
            enabled=True,
        )
        db.add(prov)
        db.commit()
        db.refresh(prov)

        model = AiModelProfile(
            provider_id=prov.id,
            model_id="import-gen-model",
            name="Import Model",
            adapter_kind="openai_standard",
            capabilities_json='{"image_generate": true}',
            enabled=True,
        )
        db.add(model)
        db.commit()
        db.refresh(model)

        task = AiTask(
            id="task_import_flow",
            task_type="image_generate",
            provider_id=prov.id,
            model_profile_id=model.id,
            status="succeeded",
            prompt_final="A magnificent crystal castle at dawn",
        )
        db.add(task)
        db.commit()

        # 生成并落盘两张结果图
        stg1 = tmp_path / "castle1.png"
        stg2 = tmp_path / "castle2.png"
        _create_dummy_image(stg1, width=800, height=600, color="gold")
        _create_dummy_image(stg2, width=800, height=600, color="silver")

        res1 = commit_generated_result(db=db, task_id=task.id, idx=0, staging_file=stg1)
        res2 = commit_generated_result(db=db, task_id=task.id, idx=1, staging_file=stg2)
        res1_id = res1.id
        res2_id = res2.id

    # 1. 单张入库 POST /api/v1/ai/results/{result_id}/import
    resp1 = client.post(
        f"/api/v1/ai/results/{res1_id}/import",
        json={"custom_name": "Crystal Castle Gold"},
        headers=headers,
    )
    assert resp1.status_code == 201
    asset_data1 = resp1.json()
    asset1_id = asset_data1["id"]
    assert asset_data1["name"] == "Crystal Castle Gold.png"
    assert asset_data1["asset_origin"] == "ai_generated"
    assert asset_data1["prompt_origin"] == "generation_prompt"
    assert asset_data1["generation_task_id"] == "task_import_flow"
    assert asset_data1["generation_result_id"] == res1_id
    assert asset_data1["source_type"] == "managed"
    assert Path(asset_data1["file_path"]).exists()

    # 验证主库通过 /assets/{id}/prompt 能查到对应提示词
    prompt_resp = client.get(f"/api/v1/assets/{asset1_id}/prompt", headers=headers)
    assert prompt_resp.status_code == 200
    assert prompt_resp.json()["prompt_text"] == "A magnificent crystal castle at dawn"
    assert prompt_resp.json()["prompt_origin"] == "generation_prompt"

    # 2. 幂等性测试：再次对同一个 result_id 执行入库，应安全幂等返回同一个 asset
    resp1_repeat = client.post(
        f"/api/v1/ai/results/{res1_id}/import",
        json={},
        headers=headers,
    )
    assert resp1_repeat.status_code == 201
    assert resp1_repeat.json()["id"] == asset1_id

    # 3. 批量入库 POST /api/v1/ai/results/batch-import
    batch_resp = client.post(
        "/api/v1/ai/results/batch-import",
        json={"result_ids": [res1_id, res2_id]},
        headers=headers,
    )
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()
    assert batch_data["total_imported"] == 2
    assert len(batch_data["items"]) == 2

    item1 = next(it for it in batch_data["items"] if it["result_id"] == res1_id)
    item2 = next(it for it in batch_data["items"] if it["result_id"] == res2_id)
    assert item1["status"] == "already_imported"
    assert item1["asset_id"] == asset1_id
    assert item2["status"] == "success"
    assert item2["asset_id"] is not None
