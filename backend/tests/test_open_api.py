"""开放接口（/api/v1/open）：局域网免鉴权守卫、默认模型解析（scene 修复）、自动入库。"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

LAN_HOST_HEADERS = {"Host": "192.168.1.50"}


def _png_bytes(width: int = 4, height: int = 4) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _seed_generation_model(app, *, bind_global_default: bool = False, bound_name: str = "IMG-BOUND") -> int:
    """种一个启用的 provider+model；bind_global_default 时按设置界面同款 scene=global 绑默认。"""
    from backend.app.models.ai.model_config import AiDefaultBinding, AiModelProfile
    from backend.app.models.ai.provider import AiProviderInstance

    with app.state.session_factory() as db:
        provider = AiProviderInstance(
            name="网关", family="openai_compatible", base_url="http://127.0.0.1:9/v1",
            credential_ref="cred-open-test", enabled=True,
        )
        db.add(provider)
        db.flush()
        bound = AiModelProfile(
            provider_id=provider.id, model_id="img-bound", name=bound_name,
            adapter_kind="openai_standard", enabled=True,
        )
        bound.capabilities = {"image_generate": {}, "image_edit": {}}
        db.add(bound)
        db.flush()
        if bind_global_default:
            db.add(AiDefaultBinding(capability="image_generate", scene="global", model_profile_id=bound.id))
        decoy = AiModelProfile(
            provider_id=provider.id, model_id="img-decoy", name="IMG-DECOY",
            adapter_kind="openai_standard", enabled=True,
        )
        decoy.capabilities = {"image_generate": {}}
        db.add(decoy)
        db.commit()
        return bound.id


# ── 守卫：开放前缀免令牌、免 Host 白名单；受保护路由行为不变 ──────────────


def test_open_info_reachable_without_token_from_lan_host(app) -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/open/info", headers=LAN_HOST_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["open_api_prefix"] == "/api/v1/open"
    assert body["default_ai_folder"] == "AI 生成"
    assert body["default_models"]["image_generate"]["model_profile_id"] is None


def test_open_cors_preflight_allows_foreign_lan_origin(app) -> None:
    with TestClient(app) as client:
        resp = client.options(
            "/api/v1/open/info",
            headers={
                **LAN_HOST_HEADERS,
                "Origin": "http://192.168.1.99:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "http://192.168.1.99:3000"


def test_protected_routes_keep_token_and_loopback_rules(app) -> None:
    with TestClient(app) as client:
        assert client.get("/api/v1/folders", headers=LAN_HOST_HEADERS).status_code == 403
        assert client.get("/api/v1/folders", headers={"Host": "127.0.0.1"}).status_code == 401


# ── 默认模型解析：设置界面写入的 scene=global 绑定必须命中 ─────────────────


def test_resolve_generation_model_prefers_global_scene_binding(app) -> None:
    from backend.app.services.ai.generation_service import resolve_generation_model

    bound_id = _seed_generation_model(app, bind_global_default=True)
    with app.state.session_factory() as db:
        resolved = resolve_generation_model(db, None, "image_generate")
    assert resolved.id == bound_id


# ── 开放生图端点：入参校验与无模型错误 ─────────────────────────────────────


def test_open_generate_requires_prompt(app) -> None:
    with TestClient(app) as client:
        resp = client.post("/api/v1/open/images/generations", headers=LAN_HOST_HEADERS, json={})
    assert resp.status_code == 422


def test_open_generate_rejects_unknown_fields(app) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/open/images/generations",
            headers=LAN_HOST_HEADERS,
            json={"prompt": "一只猫", "bogus": 1},
        )
    assert resp.status_code == 422


def test_open_generate_reference_requires_exactly_one_source(app) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/open/images/generations",
            headers=LAN_HOST_HEADERS,
            json={"prompt": "改图", "references": [{"asset_id": 1, "image_base64": "AAAA"}]},
        )
    assert resp.status_code == 422


def test_open_generate_surfaces_no_model_available(app) -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/open/images/generations",
            headers=LAN_HOST_HEADERS,
            json={"prompt": "一只猫"},
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_model_available"


def test_open_task_not_found(app) -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/open/images/tasks/aitask_missing", headers=LAN_HOST_HEADERS)
    assert resp.status_code == 404


# ── auto_import：任务成功后结果自动落『AI 生成』默认目录 ───────────────────


def test_auto_import_task_results_lands_in_default_ai_folder(app, tmp_path, monkeypatch) -> None:
    from backend.app.models.asset import Asset
    from backend.app.models.folder import Folder
    from backend.app.models.ai.task import AiResult, AiTask
    from backend.app.services.ai import storage_service
    from backend.app.services.ai.generation_service import auto_import_task_results

    monkeypatch.setattr(storage_service, "get_managed_root", lambda db: str(tmp_path / "managed"))

    sf = app.state.session_factory
    hist = tmp_path / "hist"
    hist.mkdir()
    png = hist / "res0.png"
    png.write_bytes(_png_bytes(4, 4))
    with sf() as db:
        task = AiTask(id="aitask_auto1", task_type="image_generate", status="succeeded", prompt_final="猫", params_json="{}")
        db.add(task)
        db.flush()
        result = AiResult(
            id="aires_auto1_0", task_id=task.id, idx=0, history_file_path=str(png),
            mime_type="image/png", size_bytes=png.stat().st_size, width=4, height=4,
        )
        db.add(result)
        db.commit()

    imported = auto_import_task_results(sf, task.id)
    assert [item["result_id"] for item in imported] == ["aires_auto1_0"]

    with sf() as db:
        asset = db.get(Asset, imported[0]["asset_id"])
        folder = db.get(Folder, asset.folder_id)
        assert folder.name == "AI 生成" and folder.scope_type == "general"
        assert asset.asset_origin == "ai_generated" and asset.status == "active"
        assert db.get(AiResult, "aires_auto1_0").imported_asset_id == asset.id

    # 幂等：重复执行不产生新资产
    again = auto_import_task_results(sf, task.id)
    assert again[0]["asset_id"] == imported[0]["asset_id"]


def test_auto_import_task_results_respects_custom_target_folder(app, tmp_path, monkeypatch) -> None:
    from backend.app.models.asset import Asset
    from backend.app.models.folder import Folder
    from backend.app.models.ai.task import AiResult, AiTask
    from backend.app.services.ai import storage_service
    from backend.app.services.ai.generation_service import auto_import_task_results

    monkeypatch.setattr(storage_service, "get_managed_root", lambda db: str(tmp_path / "managed"))

    sf = app.state.session_factory
    png = tmp_path / "r.png"
    png.write_bytes(_png_bytes(2, 2))
    with sf() as db:
        target = Folder(name="外部接入", scope_type="general", parent_id=None)
        db.add(target)
        db.flush()
        task = AiTask(id="aitask_auto2", task_type="image_edit", status="succeeded", prompt_final="改", params_json="{}")
        db.add(task)
        db.flush()
        db.add(AiResult(
            id="aires_auto2_0", task_id=task.id, idx=0, history_file_path=str(png),
            mime_type="image/png", size_bytes=png.stat().st_size, width=2, height=2,
        ))
        db.commit()
        target_id = target.id

    imported = auto_import_task_results(sf, task.id, target_folder_id=target_id)
    with sf() as db:
        asset = db.get(Asset, imported[0]["asset_id"])
        assert asset.folder_id == target_id
