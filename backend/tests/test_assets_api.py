from __future__ import annotations

import time

from backend.app.models.asset import Asset

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def make_source(tmp_path, name: str, content: bytes):
    source = tmp_path / name
    source.write_bytes(content)
    return source


def create_folder(iso_client, headers, name: str, scope: str = "general", project_id: int | None = None) -> int:
    response = iso_client.post(
        "/api/v1/folders",
        json={"name": name, "scope": scope, **({"project_id": project_id} if project_id else {})},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def import_file(iso_client, headers, folder_id: int, path, wait: bool = True) -> dict:
    response = iso_client.post("/api/v1/imports", json={"paths": [str(path)], "folder_id": folder_id}, headers=headers)
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    if not wait:
        return response.json()
    for _ in range(200):
        job = iso_client.get(f"/api/v1/imports/{job_id}", headers=headers).json()
        if job["status"] in TERMINAL:
            assert job["status"] == "completed", job
            return job
        time.sleep(0.05)
    raise AssertionError("import did not finish")


def test_assets_require_token(iso_client) -> None:
    response = iso_client.get("/api/v1/assets", headers={"Host": "127.0.0.1"})
    assert response.status_code == 401


def test_list_assets_by_folder(iso_client, headers, tmp_path) -> None:
    folder_a = create_folder(iso_client, headers, "画廊A")
    folder_b = create_folder(iso_client, headers, "画廊B")
    import_file(iso_client, headers, folder_a, make_source(tmp_path, "one.png", b"one"))
    import_file(iso_client, headers, folder_a, make_source(tmp_path, "two.jpg", b"two"))
    import_file(iso_client, headers, folder_b, make_source(tmp_path, "three.mp4", b"three"))

    page = iso_client.get("/api/v1/assets", params={"folder_id": folder_a}, headers=headers).json()
    assert page["total"] == 2
    assert {a["name"] for a in page["items"]} == {"one.png", "two.jpg"}

    page_b = iso_client.get("/api/v1/assets", params={"folder_id": folder_b}, headers=headers).json()
    assert page_b["total"] == 1
    assert page_b["items"][0]["asset_type"] == "video"


def test_list_assets_by_scope(iso_client, headers, tmp_path) -> None:
    project = iso_client.post("/api/v1/projects", json={"name": "画廊项目"}, headers=headers).json()
    general_folder = create_folder(iso_client, headers, "通用画廊")
    project_folder = create_folder(iso_client, headers, "项目画廊", scope="project", project_id=project["id"])
    import_file(iso_client, headers, general_folder, make_source(tmp_path, "g.png", b"g"))
    import_file(iso_client, headers, project_folder, make_source(tmp_path, "p.png", b"p"))

    general = iso_client.get("/api/v1/assets", params={"scope": "general"}, headers=headers).json()
    assert general["total"] == 1
    assert general["items"][0]["name"] == "g.png"

    proj = iso_client.get(
        "/api/v1/assets", params={"scope": "project", "project_id": project["id"]}, headers=headers
    ).json()
    assert proj["total"] == 1
    assert proj["items"][0]["name"] == "p.png"

    missing = iso_client.get("/api/v1/assets", params={"scope": "project"}, headers=headers)
    assert missing.status_code == 422


def test_assets_pagination_order(iso_client, headers, tmp_path) -> None:
    folder_id = create_folder(iso_client, headers, "分页")
    for index in range(5):
        import_file(iso_client, headers, folder_id, make_source(tmp_path, f"f{index}.png", f"content-{index}".encode()))

    first = iso_client.get(
        "/api/v1/assets", params={"folder_id": folder_id, "page": 1, "page_size": 2}, headers=headers
    ).json()
    assert first["total"] == 5
    assert len(first["items"]) == 2
    # newest first by id
    assert first["items"][0]["id"] > first["items"][1]["id"]

    second = iso_client.get(
        "/api/v1/assets", params={"folder_id": folder_id, "page": 3, "page_size": 2}, headers=headers
    ).json()
    assert len(second["items"]) == 1

    empty = iso_client.get(
        "/api/v1/assets", params={"folder_id": folder_id, "page": 9, "page_size": 2}, headers=headers
    ).json()
    assert empty["items"] == []
    assert empty["total"] == 5


def test_assets_exclude_trashed(iso_client, headers, app, tmp_path) -> None:
    folder_id = create_folder(iso_client, headers, "回收验证")
    import_file(iso_client, headers, folder_id, make_source(tmp_path, "trash-me.png", b"t"))

    with app.state.session_factory() as session:
        asset = session.query(Asset).one()
        asset.status = "trashed"
        session.commit()

    page = iso_client.get("/api/v1/assets", params={"folder_id": folder_id}, headers=headers).json()
    assert page["total"] == 0
