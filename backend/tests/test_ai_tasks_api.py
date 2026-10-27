from __future__ import annotations

import asyncio
from datetime import datetime
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.models.ai.provider import AiProviderInstance
from backend.app.models.ai.model_config import AiModelProfile
from backend.app.models.ai.task import AiTask, AiTaskItem, AiTaskReference, AiResult
from backend.app.models.asset import Asset
from backend.app.services.ai.credentials import CredentialManager
from backend.app.services.ai.task_scheduler import (
    AiTaskScheduler,
    get_task_scheduler,
    init_task_scheduler,
)


def test_task_scheduler_concurrency_and_state_machine(app: FastAPI) -> None:
    session_factory = app.state.session_factory

    scheduler = AiTaskScheduler(
        session_factory=session_factory,
        max_global_concurrency=2,
        per_provider_concurrency=1,
    )

    with session_factory() as db:
        # 1. 创建任务
        task1 = scheduler.create_task(
            db=db,
            task_type="image_generate",
            prompt_final="A high-tech cyberpunk laboratory",
            params={"width": 1024, "height": 1024},
        )
        assert task1.status == "queued"
        assert task1.params["width"] == 1024
        task1_id = task1.id

    # 2. 状态合法流转 queued -> running -> succeeded
    scheduler.update_task_status(task1_id, "running")
    with session_factory() as db:
        t1 = db.query(AiTask).filter(AiTask.id == task1_id).first()
        assert t1.status == "running"

    scheduler.update_task_status(task1_id, "succeeded", progress_pct=100)
    with session_factory() as db:
        t1 = db.query(AiTask).filter(AiTask.id == task1_id).first()
        assert t1.status == "succeeded"
        assert t1.progress_pct == 100
        assert t1.finished_at is not None

    # 3. 非法流转（succeeded -> running）被阻止
    scheduler.update_task_status(task1_id, "running")
    with session_factory() as db:
        t1 = db.query(AiTask).filter(AiTask.id == task1_id).first()
        assert t1.status == "succeeded"


def test_task_cancel_queued_and_running(app: FastAPI) -> None:
    session_factory = app.state.session_factory
    scheduler = AiTaskScheduler(session_factory=session_factory)

    with session_factory() as db:
        # 1. 取消 queued 任务 -> 直接 canceled
        task_q = scheduler.create_task(db=db, task_type="image_generate")
        assert task_q.status == "queued"
        task_q_id = task_q.id

    res = scheduler.request_cancel(task_q_id)
    assert res is True
    with session_factory() as db:
        tq = db.query(AiTask).filter(AiTask.id == task_q_id).first()
        assert tq.status == "canceled"

    with session_factory() as db:
        # 2. 取消 running 任务 -> cancel_requested 并置 event
        task_r = scheduler.create_task(db=db, task_type="image_edit")
        task_r_id = task_r.id
    scheduler.update_task_status(task_r_id, "running")

    # 模拟加入事件
    cancel_evt = asyncio.Event()
    scheduler._cancel_events[task_r_id] = cancel_evt

    res = scheduler.request_cancel(task_r_id)
    assert res is True
    with session_factory() as db:
        tr = db.query(AiTask).filter(AiTask.id == task_r_id).first()
        assert tr.status == "cancel_requested"
    assert cancel_evt.is_set()


def test_task_startup_recovery(app: FastAPI) -> None:
    session_factory = app.state.session_factory
    scheduler = AiTaskScheduler(session_factory=session_factory)

    with session_factory() as db:
        t_run = scheduler.create_task(db=db, task_type="image_generate")
        t_run_id = t_run.id
        t_cancel_req = scheduler.create_task(db=db, task_type="image_generate")
        t_cancel_req_id = t_cancel_req.id
        t_queued = scheduler.create_task(db=db, task_type="image_generate")
        t_queued_id = t_queued.id

    scheduler.update_task_status(t_run_id, "running")
    scheduler.update_task_status(t_cancel_req_id, "running")
    scheduler.update_task_status(t_cancel_req_id, "cancel_requested")

    # 模拟重启恢复
    summary = scheduler.recover_interrupted_tasks_on_startup()
    assert summary["recovery_needed"] == 2
    assert summary["canceled"] == 1

    with session_factory() as db:
        tr = db.query(AiTask).filter(AiTask.id == t_run_id).first()
        tc = db.query(AiTask).filter(AiTask.id == t_cancel_req_id).first()
        tq = db.query(AiTask).filter(AiTask.id == t_queued_id).first()

        assert tr.status == "recovery_needed"
        assert tr.error_code == "process_interrupted"
        assert tc.status == "recovery_needed"
        assert tq.status == "canceled"


def test_task_retry_mechanism(app: FastAPI) -> None:
    session_factory = app.state.session_factory
    scheduler = AiTaskScheduler(session_factory=session_factory)

    with session_factory() as db:
        t_failed = scheduler.create_task(
            db=db,
            task_type="image_generate",
            prompt_final="An astronaut on Mars",
            params={"steps": 30},
        )
        t_failed_id = t_failed.id
        # 添加一个参考图
        ref = AiTaskReference(
            task_id=t_failed.id,
            seq=0,
            role="style",
            source_kind="local_upload",
            snapshot_path="/snapshots/ref1.png",
            sha256="abc12345",
        )
        db.add(ref)
        db.commit()

    scheduler.update_task_status(t_failed_id, "running")
    scheduler.update_task_status(t_failed_id, "failed", error_code="timeout", error_message="Upstream timeout")

    # 执行 retry
    with session_factory() as db:
        new_task = scheduler.retry_task(db=db, task_id=t_failed_id)
        assert new_task.id != t_failed_id
        assert new_task.retry_of == t_failed_id
        assert new_task.status == "queued"
        assert new_task.prompt_final == "An astronaut on Mars"
        assert len(new_task.references) == 1
        assert new_task.references[0].snapshot_path == "/snapshots/ref1.png"


def test_ai_tasks_api(client: TestClient, headers: dict[str, str], app: FastAPI) -> None:
    session_factory = app.state.session_factory
    with session_factory() as db:
        # 1. 创建测试 Provider 与 Model
        prov = AiProviderInstance(
            family="openai_compatible",
            name="Test Task Provider",
            base_url="https://api.example.com/v1",
            credential_ref="test_cred_ref",
            enabled=True,
        )
        db.add(prov)
        db.commit()
        db.refresh(prov)
        prov_id = prov.id

        model = AiModelProfile(
            provider_id=prov.id,
            model_id="test-gen-model",
            name="Test Generation Model",
            adapter_kind="openai_standard",
            capabilities_json='{"image_generate": true}',
            enabled=True,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        model_id = model.id

        # 2. 插入任务
        t = AiTask(
            id="aitask_test_12345",
            task_type="image_generate",
            provider_id=prov_id,
            model_profile_id=model_id,
            status="queued",
            prompt_final="Cyberpunk street in rain",
            params_json='{"width": 1024, "height": 1024}',
        )
        db.add(t)
        db.commit()

    # 3. GET /api/v1/ai/tasks 列表
    resp = client.get("/api/v1/ai/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    task_match = next((item for item in data["items"] if item["id"] == "aitask_test_12345"), None)
    assert task_match is not None
    assert task_match["provider_name"] == "Test Task Provider"
    assert task_match["model_name"] == "Test Generation Model"

    # 4. GET /api/v1/ai/tasks/{id} 详情
    detail_resp = client.get("/api/v1/ai/tasks/aitask_test_12345", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == "aitask_test_12345"
    assert detail["params"]["width"] == 1024
    assert isinstance(detail["items"], list)
    assert isinstance(detail["references"], list)
    assert isinstance(detail["results"], list)

    # 5. POST /api/v1/ai/tasks/{id}/cancel
    cancel_resp = client.post("/api/v1/ai/tasks/aitask_test_12345/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    c_data = cancel_resp.json()
    assert c_data["cancelled"] is True
    assert c_data["status"] == "canceled"

    # 6. POST /api/v1/ai/tasks/{id}/retry
    retry_resp = client.post("/api/v1/ai/tasks/aitask_test_12345/retry", headers=headers)
    assert retry_resp.status_code == 200
    r_data = retry_resp.json()
    assert r_data["retry_of"] == "aitask_test_12345"
    assert r_data["status"] == "queued"
    assert r_data["id"] != "aitask_test_12345"


def test_staging_upload_and_multi_source_reference(client: TestClient, headers: dict[str, str], app: FastAPI) -> None:
    import base64
    import io
    from PIL import Image
    from backend.app.models.asset import Asset
    from backend.app.services.ai.credentials import CredentialManager

    session_factory = app.state.session_factory

    # 1. 测试临时参考图上传（Base64 形式，免 multipart 依赖）
    img_buf = io.BytesIO()
    Image.new("RGB", (32, 32), color="red").save(img_buf, format="PNG")
    png_bytes = img_buf.getvalue()
    b64_str = base64.b64encode(png_bytes).decode("ascii")

    upload_resp = client.post(
        "/api/v1/ai/tasks/staging/upload",
        json={"filename": "my_sketch.png", "content_base64": b64_str},
        headers=headers,
    )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    assert upload_data["upload_id"].startswith("up_")
    assert upload_data["width"] == 32
    assert upload_data["height"] == 32
    upload_id = upload_data["upload_id"]

    # 2. 准备 Asset 与 Provider / Model
    with session_factory() as db:
        prov = AiProviderInstance(
            family="openai_compatible",
            name="Ref Test Provider",
            base_url="https://api.example.com/v1",
            credential_ref="ref_cred_key",
            enabled=True,
        )
        db.add(prov)
        db.commit()
        db.refresh(prov)
        CredentialManager.save_credential("sk-dummy", ref_id=prov.credential_ref)

        model = AiModelProfile(
            provider_id=prov.id,
            model_id="dall-e-3",
            name="DALL-E 3 Ref",
            adapter_kind="openai_standard",
            capabilities_json='{"image_generate": true}',
            enabled=True,
        )
        db.add(model)
        db.commit()
        db.refresh(model)

        # 临时创建测试资产文件
        import tempfile
        tmp_asset_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp_asset_file.write(png_bytes)
        tmp_asset_file.close()

        asset = Asset(
            name="library_reference.png",
            file_path=tmp_asset_file.name,
            size_bytes=len(png_bytes),
            extension="png",
            source_type="managed",
            asset_type="image",
            status="active",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        asset_id = asset.id

    # 3. 提交包含多源参考图的任务 (本地上传 + 库资产)
    task_payload = {
        "prompt": "Cyberpunk character with matching style",
        "model_profile_id": model.id,
        "references": [
            {"source_kind": "local_upload", "source_id": upload_id, "role": "style"},
            {"source_kind": "asset", "source_id": str(asset_id), "role": "character"},
        ],
    }

    submit_resp = client.post("/api/v1/ai/tasks", json=task_payload, headers=headers)
    assert submit_resp.status_code == 201
    task_res = submit_resp.json()
    task_id = task_res["id"]

    # 4. 验证任务详情中的 references 已经生成快照记录
    detail_resp = client.get(f"/api/v1/ai/tasks/{task_id}", headers=headers)
    assert detail_resp.status_code == 200
    refs = detail_resp.json()["references"]
    assert len(refs) == 2
    assert refs[0]["source_kind"] == "local_upload"
    assert refs[0]["role"] == "style"
    assert refs[1]["source_kind"] == "asset"
    assert refs[1]["role"] == "character"


def test_image_edit_task_submission(client: TestClient, headers: dict[str, str], app: FastAPI) -> None:
    session_factory = app.state.session_factory

    with session_factory() as db:
        prov = AiProviderInstance(
            family="openai_compatible",
            name="Edit Test Provider",
            base_url="https://api.example.com/v1",
            credential_ref="edit_cred_key",
            enabled=True,
        )
        db.add(prov)
        db.commit()
        db.refresh(prov)
        CredentialManager.save_credential("sk-dummy-edit", ref_id=prov.credential_ref)

        model = AiModelProfile(
            provider_id=prov.id,
            model_id="dall-e-2",
            name="DALL-E 2 Edit",
            adapter_kind="openai_standard",
            capabilities_json='{"image_edit": true}',
            enabled=True,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        model_id = model.id

    # 1. 未提供参考图时提交 image_edit 任务应被拒绝
    fail_payload = {
        "task_type": "image_edit",
        "prompt": "Make background sunset",
        "model_profile_id": model_id,
        "references": [],
    }
    fail_resp = client.post("/api/v1/ai/tasks", json=fail_payload, headers=headers)
    assert fail_resp.status_code == 422
    assert fail_resp.json()["error"]["code"] == "missing_reference"

    # 2. 正常提交 image_edit 任务（带参考图）
    upload_res = client.post(
        "/api/v1/ai/tasks/staging/upload",
        json={"filename": "orig.png", "content_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="},
        headers=headers,
    )
    assert upload_res.status_code == 201
    upload_id = upload_res.json()["upload_id"]

    success_payload = {
        "task_type": "image_edit",
        "prompt": "Change sky to dramatic sunset",
        "model_profile_id": model_id,
        "references": [
            {"source_kind": "local_upload", "source_id": upload_id, "role": "reference"}
        ],
    }
    ok_resp = client.post("/api/v1/ai/tasks", json=success_payload, headers=headers)
    assert ok_resp.status_code == 201
    task_data = ok_resp.json()
    assert task_data["task_type"] == "image_edit"


def test_task_variant_and_retry_compatibility(client: TestClient, headers: dict[str, str], app: FastAPI) -> None:
    session_factory = app.state.session_factory

    with session_factory() as db:
        prov = AiProviderInstance(
            family="openai_compatible",
            name="Variant Test Provider",
            base_url="https://api.example.com/v1",
            credential_ref="variant_cred_key",
            enabled=True,
        )
        db.add(prov)
        db.commit()
        db.refresh(prov)
        CredentialManager.save_credential("sk-dummy-variant", ref_id=prov.credential_ref)

        model = AiModelProfile(
            provider_id=prov.id,
            model_id="flux-dev",
            name="FLUX.1 Dev",
            adapter_kind="openai_standard",
            capabilities_json='{"image_generate": true}',
            enabled=True,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        model_id = model.id
        prov_id = prov.id

    # 1. 提交初代生图任务
    init_payload = {
        "task_type": "image_generate",
        "prompt": "Cyberpunk street in rain",
        "model_profile_id": model_id,
        "params": {"size": "1024x1024", "seed": 42},
    }
    r1 = client.post("/api/v1/ai/tasks", json=init_payload, headers=headers)
    assert r1.status_code == 201
    task1_id = r1.json()["id"]

    # 2. 提交变体任务（带 retry_of 参数指向 task1_id）
    variant_payload = {
        "task_type": "image_generate",
        "prompt": "Cyberpunk street in snow at night",  # 微调了 prompt
        "model_profile_id": model_id,
        "params": {"size": "1024x1024", "seed": 43},
        "retry_of": task1_id,
    }
    r2 = client.post("/api/v1/ai/tasks", json=variant_payload, headers=headers)
    assert r2.status_code == 201
    task2_data = r2.json()
    assert task2_data["retry_of"] == task1_id
    assert task2_data["id"] != task1_id

    # 3. 取消任务 1 使其处于终止态以便测试重试
    c_resp = client.post(f"/api/v1/ai/tasks/{task1_id}/cancel", headers=headers)
    assert c_resp.status_code == 200

    # 测试重试兼容性校验：当模型被禁用时，尝试一键重试应返回 400 model_unavailable
    with session_factory() as db:
        m = db.get(AiModelProfile, model_id)
        assert m is not None
        m.enabled = False
        db.commit()

    r3 = client.post(f"/api/v1/ai/tasks/{task1_id}/retry", headers=headers)
    assert r3.status_code == 400
    assert r3.json()["error"]["code"] == "model_unavailable"

    # 恢复模型但禁用 Provider 时，重试应返回 400 provider_unavailable
    with session_factory() as db:
        m = db.get(AiModelProfile, model_id)
        assert m is not None
        m.enabled = True
        p = db.get(AiProviderInstance, prov_id)
        assert p is not None
        p.enabled = False
        db.commit()

    r4 = client.post(f"/api/v1/ai/tasks/{task1_id}/retry", headers=headers)
    assert r4.status_code == 400
    assert r4.json()["error"]["code"] == "provider_unavailable"


def test_batch_reverse_tasks_and_commit(client: TestClient, headers: dict[str, str], app: FastAPI) -> None:
    session_factory = app.state.session_factory
    # 准备具备 image_understand 能力的 Provider 和 Model Profile
    with session_factory() as db:
        prov = AiProviderInstance(
            family="openai_compatible",
            name="Vision Batch Provider",
            base_url="https://api.example.com/v1",
            credential_ref="vision_batch_cred_key",
            enabled=True,
        )
        db.add(prov)
        db.commit()
        db.refresh(prov)
        CredentialManager.save_credential("sk-dummy-vision", ref_id=prov.credential_ref)

        model = AiModelProfile(
            provider_id=prov.id,
            model_id="gpt-4o-mini",
            name="GPT-4o Mini Vision",
            adapter_kind="openai_standard",
            capabilities_json='{"image_understand": true}',
            enabled=True,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        model_id = model.id

        a1 = Asset(
            name="batch_img1.png",
            file_path="F:/trae_project/Ryan_DAM/dummy1.png",
            source_type="managed",
            asset_type="image",
            size_bytes=1024,
            prompt_text=None,
            prompt_revision=1,
        )
        a2 = Asset(
            name="batch_img2.png",
            file_path="F:/trae_project/Ryan_DAM/dummy2.png",
            source_type="managed",
            asset_type="image",
            size_bytes=2048,
            prompt_text="existing prompt",
            prompt_revision=1,
        )
        db.add_all([a1, a2])
        db.commit()
        db.refresh(a1)
        db.refresh(a2)
        asset1_id = a1.id
        asset2_id = a2.id

    # 1. 提交批量反推任务
    submit_payload = {
        "asset_ids": [asset1_id, asset2_id],
        "template_id": None,
        "model_profile_id": model_id,
        "user_instruction": "请分析画面要素",
    }
    r = client.post("/api/v1/ai/tasks/batch-reverse", json=submit_payload, headers=headers)
    assert r.status_code == 201
    task_data = r.json()
    task_id = task_data["id"]
    assert task_data["task_type"] == "batch_reverse"
    assert task_data["items_count"] == 2

    # 2. 查询任务详情获取 items
    detail_resp = client.get(f"/api/v1/ai/tasks/{task_id}", headers=headers)
    assert detail_resp.status_code == 200
    items = detail_resp.json()["items"]
    assert len(items) == 2
    item1 = next(it for it in items if it["asset_id"] == asset1_id)
    item2 = next(it for it in items if it["asset_id"] == asset2_id)

    # 3. 模拟 runner 反推成功，手动更新 items 状态与草稿 (模拟异步执行完成)
    with session_factory() as db:
        it1 = db.get(AiTaskItem, item1["id"])
        it2 = db.get(AiTaskItem, item2["id"])
        assert it1 is not None and it2 is not None
        it1.status = "succeeded"
        it1.draft_prompt_text = "reversed prompt 1"
        it2.status = "succeeded"
        it2.draft_prompt_text = "reversed prompt 2"
        db.commit()

    # 4. 测试修改单个 item 草稿接口 PUT /api/v1/ai/tasks/{task_id}/items/{item_id}
    edit_resp = client.put(
        f"/api/v1/ai/tasks/{task_id}/items/{item1['id']}",
        json={"draft_prompt_text": "manually edited prompt 1"},
        headers=headers,
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["draft_prompt_text"] == "manually edited prompt 1"

    # 5. 测试提交审查：未勾选 allow_overwrite 时，已有 prompt 的 asset2 应被标记为 conflict
    commit_payload = {
        "item_ids": [item1["id"], item2["id"]],
        "allow_overwrite": False,
    }
    c_resp = client.post(f"/api/v1/ai/tasks/{task_id}/commit-items", json=commit_payload, headers=headers)
    assert c_resp.status_code == 200
    res_data = c_resp.json()
    assert res_data["committed_count"] == 1
    assert res_data["conflict_count"] == 1
    detail2 = next(d for d in res_data["details"] if d["item_id"] == item2["id"])
    assert detail2["status"] == "conflict"
    assert "已有提示词" in detail2["reason"]

    # 验证 asset1 已成功写入
    with session_factory() as db:
        refreshed_a1 = db.get(Asset, asset1_id)
        assert refreshed_a1 is not None
        assert refreshed_a1.prompt_text == "manually edited prompt 1"
        assert refreshed_a1.prompt_origin == "ai_reverse"
        assert refreshed_a1.prompt_revision == 2

    # 6. 允许覆盖提交 asset2
    commit_payload2 = {
        "item_ids": [item2["id"]],
        "allow_overwrite": True,
    }
    c_resp2 = client.post(f"/api/v1/ai/tasks/{task_id}/commit-items", json=commit_payload2, headers=headers)
    assert c_resp2.status_code == 200
    res_data2 = c_resp2.json()
    assert res_data2["committed_count"] == 1
    assert res_data2["conflict_count"] == 0

    with session_factory() as db:
        refreshed_a2 = db.get(Asset, asset2_id)
        assert refreshed_a2 is not None
        assert refreshed_a2.prompt_text == "reversed prompt 2"
        assert refreshed_a2.prompt_revision == 2



