from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import create_app


def make_app(db_path) -> TestClient:
    return TestClient(create_app("test-token", db_path=str(db_path)))


def test_projects_require_token(client) -> None:
    response = client.get("/api/v1/projects", headers={"Host": "127.0.0.1"})
    assert response.status_code == 401


def test_create_list_and_rename_project(client, headers) -> None:
    created = client.post("/api/v1/projects", json={"name": " 旅行视频 "}, headers=headers)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "旅行视频"

    renamed = client.patch(f"/api/v1/projects/{body['id']}", json={"name": "旅行视频 V2"}, headers=headers)
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "旅行视频 V2"

    listed = client.get("/api/v1/projects", headers=headers)
    assert [p["name"] for p in listed.json()] == ["旅行视频 V2"]


def test_duplicate_project_name_rejected(client, headers) -> None:
    assert client.post("/api/v1/projects", json={"name": "Demo"}, headers=headers).status_code == 201
    duplicate = client.post("/api/v1/projects", json={"name": "demo"}, headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_name"


def test_rename_missing_project_returns_not_found(client, headers) -> None:
    response = client.patch("/api/v1/projects/999", json={"name": "Ghost"}, headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_empty_project_name_rejected(client, headers) -> None:
    response = client.post("/api/v1/projects", json={"name": "   "}, headers=headers)
    assert response.status_code == 422


def test_delete_project_protection(client, headers) -> None:
    project = client.post("/api/v1/projects", json={"name": "Blocked"}, headers=headers).json()
    client.post("/api/v1/folders", json={"name": "子目录", "scope": "project", "project_id": project["id"]}, headers=headers)

    refused = client.delete(f"/api/v1/projects/{project['id']}", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "project_not_empty"

    still_there = client.get("/api/v1/projects", headers=headers)
    assert len(still_there.json()) == 1


def test_project_stats(iso_client, headers) -> None:
    project = iso_client.post("/api/v1/projects", json={"name": "统计项目"}, headers=headers).json()
    empty_stats = iso_client.get(f"/api/v1/projects/{project['id']}/stats", headers=headers)
    assert empty_stats.status_code == 200
    assert empty_stats.json()["subfolder_count"] == 0

    parent = iso_client.post(
        "/api/v1/folders", json={"name": "场景A", "scope": "project", "project_id": project["id"]}, headers=headers
    ).json()
    iso_client.post(
        "/api/v1/folders",
        json={"name": "子场景", "scope": "project", "project_id": project["id"], "parent_id": parent["id"]},
        headers=headers,
    )
    stats = iso_client.get(f"/api/v1/projects/{project['id']}/stats", headers=headers).json()
    assert stats["project_name"] == "统计项目"
    assert stats["subfolder_count"] == 2

    missing = iso_client.get("/api/v1/projects/999/stats", headers=headers)
    assert missing.status_code == 404


def test_project_cascade_delete(iso_client, headers, tmp_path) -> None:
    import time

    def wait_import(job_id: int) -> None:
        for _ in range(300):
            res = iso_client.get(f"/api/v1/imports/{job_id}", headers=headers).json()
            if res["status"] in {"completed", "failed"}:
                assert res["status"] == "completed"
                return
            time.sleep(0.02)
        raise AssertionError("import timeout")

    project = iso_client.post("/api/v1/projects", json={"name": "韩峉塔"}, headers=headers).json()
    parent = iso_client.post(
        "/api/v1/folders", json={"name": "角色", "scope": "project", "project_id": project["id"]}, headers=headers
    ).json()
    child = iso_client.post(
        "/api/v1/folders",
        json={"name": "道具", "scope": "project", "project_id": project["id"], "parent_id": parent["id"]},
        headers=headers,
    ).json()

    # Managed asset inside the nested project folder
    src = tmp_path / "角色图.png"
    src.write_bytes(b"png-managed")
    job = iso_client.post(
        "/api/v1/imports", json={"paths": [str(src)], "folder_id": child["id"]}, headers=headers
    ).json()
    wait_import(job["id"])

    # External source linked into the same project subtree
    ext_root = tmp_path / "外部参考库"
    ext_root.mkdir()
    ext_file = ext_root / "参考.md"
    ext_file.write_text("# ref", encoding="utf-8")
    link = iso_client.post(
        "/api/v1/external-sources",
        json={"root_path": str(ext_root), "target_folder_id": parent["id"]},
        headers=headers,
    )
    assert link.status_code == 201

    stats = iso_client.get(f"/api/v1/projects/{project['id']}/stats", headers=headers).json()
    assert stats["subfolder_count"] == 2
    assert stats["managed_asset_count"] == 1
    assert stats["external_asset_count"] == 1

    # Without cascade still protected
    refused = iso_client.delete(f"/api/v1/projects/{project['id']}", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "project_not_empty"

    deleted = iso_client.delete(f"/api/v1/projects/{project['id']}?cascade=true", headers=headers)
    assert deleted.status_code == 204

    # Project and its folder tree gone
    assert iso_client.get("/api/v1/projects", headers=headers).json() == []
    assert iso_client.get(f"/api/v1/projects/{project['id']}/stats", headers=headers).status_code == 404
    assert iso_client.get("/api/v1/folders/tree?scope=general", headers=headers).json() == []

    # Managed asset landed in trash, external index removed without trashing
    trash = iso_client.get("/api/v1/trash", headers=headers).json()
    assert trash["total"] == 1
    assert trash["items"][0]["name"] == "角色图.png"
    assert iso_client.get("/api/v1/external-sources", headers=headers).json() == []
    remaining = iso_client.get("/api/v1/assets", params={"limit": 50}, headers=headers).json()
    assert all(a["name"] != "参考.md" for a in remaining["items"])

    # Source files untouched on disk (external never deleted, managed kept for restore)
    assert ext_file.read_text(encoding="utf-8") == "# ref"
    restored = iso_client.post(f"/api/v1/trash/{trash['items'][0]['id']}/restore", headers=headers)
    assert restored.status_code == 204


def test_database_survives_app_restart(tmp_path, headers) -> None:
    db_path = tmp_path / "restart.sqlite3"
    with make_app(db_path) as first:
        created = first.post("/api/v1/projects", json={"name": "跨重启"}, headers=headers).json()
        first.patch(
            "/api/v1/settings",
            json={"managed_root": str(tmp_path / "assets")},
            headers=headers,
        )

    with make_app(db_path) as second:
        projects = second.get("/api/v1/projects", headers=headers).json()
        assert [p["id"] for p in projects] == [created["id"]]
        settings = second.get("/api/v1/settings", headers=headers).json()
        assert settings["managed_root"] == str(tmp_path / "assets")
