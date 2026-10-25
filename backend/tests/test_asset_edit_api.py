from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from backend.app.models.asset import Asset

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def _wait_import(iso_client, headers, job_id: int) -> dict:
    for _ in range(300):
        final = iso_client.get(f"/api/v1/imports/{job_id}", headers=headers).json()
        if final["status"] in TERMINAL:
            assert final["status"] == "completed", final
            return final
        time.sleep(0.05)
    raise AssertionError("import did not finish")


def _make_one(iso_client, headers, tmp_path, folder_name: str, filename: str, content: str) -> int:
    existing = iso_client.get("/api/v1/folders/tree?scope=general", headers=headers).json()

    def find_folder(nodes, name):
        for node in nodes:
            if node["name"] == name:
                return node
            hit = find_folder(node["children"], name)
            if hit:
                return hit
        return None

    node = find_folder(existing, folder_name)
    folder_id = node["id"] if node else iso_client.post(
        "/api/v1/folders", json={"name": folder_name, "scope": "general"}, headers=headers
    ).json()["id"]
    source = tmp_path / filename
    source.write_text(content if isinstance(content, str) else content.decode(), encoding="utf-8")
    job = iso_client.post("/api/v1/imports", json={"paths": [str(source)], "folder_id": folder_id}, headers=headers).json()
    _wait_import(iso_client, headers, job["id"])
    assets = iso_client.get("/api/v1/assets", params={"folder_id": folder_id}, headers=headers).json()
    return assets["items"][0]["id"]


def _wait_thumbnail_settled(app, asset_id: int) -> None:
    """Media imports enqueue thumbnail work that briefly reads the file; wait for it."""
    for _ in range(200):
        if _row(app, asset_id).thumbnail_status != "pending":
            return
        time.sleep(0.05)


def _row(app, asset_id: int) -> Asset:
    session_factory: sessionmaker = app.state.session_factory
    with session_factory() as session:
        return session.get(Asset, asset_id)


def _external_asset(app, tmp_path, name: str = "外部图.png") -> int:
    source = tmp_path / name
    source.write_bytes(b"external-bytes")
    session_factory: sessionmaker = app.state.session_factory
    with session_factory() as session:
        from backend.app.models.folder import Folder

        folder = Folder(name="外部来源目录", scope_type="general", project_id=None, parent_id=None, sort_order=1)
        session.add(folder)
        session.flush()
        asset = Asset(
            folder_id=folder.id,
            name=name,
            extension="png",
            asset_type="image",
            size_bytes=source.stat().st_size,
            file_path=str(source),
            source_type="external",
            thumbnail_status="none",
        )
        session.add(asset)
        session.commit()
        return asset.id


def test_rename_keeps_extension_and_syncs_disk(iso_client, headers, app, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "重命名目录", "hero.png", "image-bytes")
    old_path = Path(_row(app, asset_id).file_path)

    response = iso_client.patch(f"/api/v1/assets/{asset_id}", json={"name": "新名字"}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "新名字.png"
    assert body["extension"] == "png"

    row = _row(app, asset_id)
    new_path = Path(row.file_path)
    assert new_path.is_file()
    assert new_path.parent == old_path.parent
    assert not old_path.exists()
    assert new_path.read_text(encoding="utf-8") == "image-bytes"
    assert row.name == "新名字.png"


def test_rename_with_explicit_same_extension_and_case_change(iso_client, headers, app, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "重命名扩展", "clip.mp4", b"video")
    _wait_thumbnail_settled(app, asset_id)

    response = iso_client.patch(f"/api/v1/assets/{asset_id}", json={"name": "CLIP.MP4"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "CLIP.MP4"
    assert Path(_row(app, asset_id).file_path).is_file()


def test_rename_rejects_extension_change(iso_client, headers, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "扩展拒绝", "photo.png", "x")
    response = iso_client.patch(f"/api/v1/assets/{asset_id}", json={"name": "photo.jpg"}, headers=headers)
    assert response.status_code == 422
    assert "扩展名" in response.json()["error"]["message"]


def test_rename_conflict_in_same_folder(iso_client, headers, app, tmp_path) -> None:
    first = _make_one(iso_client, headers, tmp_path, "冲突目录", "first.txt", "a")
    second = _make_one(iso_client, headers, tmp_path, "冲突目录", "second.txt", "b")
    assert _row(app, first).folder_id == _row(app, second).folder_id

    response = iso_client.patch(f"/api/v1/assets/{second}", json={"name": "first.txt"}, headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_name"
    row = _row(app, second)
    assert row.name == "second.txt"
    assert Path(row.file_path).is_file()


def test_rename_validation_and_missing(iso_client, headers, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "重命名校验", "doc.txt", "x")

    assert iso_client.patch(f"/api/v1/assets/{asset_id}", json={"name": "  "}, headers=headers).status_code == 422
    bad = iso_client.patch(f"/api/v1/assets/{asset_id}", json={"name": "a<b>.txt"}, headers=headers)
    assert bad.status_code == 422
    assert iso_client.patch("/api/v1/assets/99999", json={"name": "任意"}, headers=headers).status_code == 404


def test_rename_missing_managed_file_404(iso_client, headers, app, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "重命名丢文件", "lost.txt", "x")
    Path(_row(app, asset_id).file_path).unlink()  # file vanishes without a rescan

    response = iso_client.patch(f"/api/v1/assets/{asset_id}", json={"name": "renamed.txt"}, headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "content_unavailable"
    assert _row(app, asset_id).name == "lost.txt", "row keeps its old name when the file is gone"


def test_rename_external_readonly(iso_client, headers, app, tmp_path) -> None:
    asset_id = _external_asset(app, tmp_path)
    response = iso_client.patch(f"/api/v1/assets/{asset_id}", json={"name": "新名字.png"}, headers=headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "external_readonly"
    row = _row(app, asset_id)
    assert row.name == "外部图.png"
    assert Path(row.file_path).is_file()


def test_move_updates_folder_only(iso_client, headers, app, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "移动来源", "mover.txt", "m")
    physical = Path(_row(app, asset_id).file_path)
    target = iso_client.post("/api/v1/folders", json={"name": "移动目标", "scope": "general"}, headers=headers).json()

    response = iso_client.post(f"/api/v1/assets/{asset_id}/move", json={"folder_id": target["id"]}, headers=headers)
    assert response.status_code == 200
    assert response.json()["folder_id"] == target["id"]

    row = _row(app, asset_id)
    assert Path(row.file_path) == physical, "physical file must not move"
    assert physical.is_file()

    assets = iso_client.get("/api/v1/assets", params={"folder_id": target["id"]}, headers=headers).json()
    assert assets["total"] == 1


def test_move_guards(iso_client, headers, app, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "移动守卫", "guard.txt", "g")

    same = iso_client.post(
        "/api/v1/assets/{0}/move".format(asset_id),
        json={"folder_id": _row(app, asset_id).folder_id},
        headers=headers,
    )
    assert same.status_code == 400

    # 跨项目与跨库移动现在得到允许
    project = iso_client.post("/api/v1/projects", json={"name": "移动项目"}, headers=headers).json()
    project_folder = iso_client.post(
        "/api/v1/folders", json={"name": "项目内目录", "scope": "project", "project_id": project["id"]}, headers=headers
    ).json()
    cross = iso_client.post(
        f"/api/v1/assets/{asset_id}/move", json={"folder_id": project_folder["id"]}, headers=headers
    )
    assert cross.status_code == 200
    assert cross.json()["folder_id"] == project_folder["id"]

    unknown = iso_client.post(f"/api/v1/assets/{asset_id}/move", json={"folder_id": 987654}, headers=headers)
    assert unknown.status_code == 404


def test_move_external_readonly(iso_client, headers, app, tmp_path) -> None:
    asset_id = _external_asset(app, tmp_path)
    target = iso_client.post("/api/v1/folders", json={"name": "外部移动目标", "scope": "general"}, headers=headers).json()
    response = iso_client.post(f"/api/v1/assets/{asset_id}/move", json={"folder_id": target["id"]}, headers=headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "external_readonly"
