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
