from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from backend.app.models.asset import Asset
from backend.tests.test_bulk_api import make_assets

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def _wait_import(iso_client, headers, job_id: int) -> dict:
    for _ in range(300):
        final = iso_client.get(f"/api/v1/imports/{job_id}", headers=headers).json()
        if final["status"] in TERMINAL:
            assert final["status"] == "completed", final
            return final
        time.sleep(0.05)
    raise AssertionError("import did not finish")


def _make_one(iso_client, headers, tmp_path, name: str) -> int:
    folder = iso_client.post("/api/v1/folders", json={"name": name, "scope": "general"}, headers=headers).json()
    source = tmp_path / f"{name}.txt"
    source.write_text(f"content {name}", encoding="utf-8")
    job = iso_client.post("/api/v1/imports", json={"paths": [str(source)], "folder_id": folder["id"]}, headers=headers).json()
    _wait_import(iso_client, headers, job["id"])
    assets = iso_client.get("/api/v1/assets", params={"folder_id": folder["id"]}, headers=headers).json()
    return assets["items"][0]["id"]


def _asset_row(app, asset_id: int) -> Asset | None:
    session_factory: sessionmaker = app.state.session_factory
    with session_factory() as session:
        return session.get(Asset, asset_id)


def _managed_root_of(app, asset_id: int) -> Path:
    row = _asset_row(app, asset_id)
    assert row is not None
    return Path(row.file_path).parents[2]


def _make_external(app, tmp_path, name: str = "外部素材.png") -> tuple[int, Path]:
    """Insert an external index row directly (ticket 17 adds the scan API)."""
    source = tmp_path / name
    source.write_bytes(b"external-source-bytes")
    session_factory: sessionmaker = app.state.session_factory
    with session_factory() as session:
        from backend.app.models.folder import Folder

        folder = Folder(name="外部目录", scope_type="general", project_id=None, parent_id=None, sort_order=1)
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
        return asset.id, source


def test_delete_managed_moves_file_to_trash(iso_client, headers, app, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "回收甲")
    managed_root = _managed_root_of(app, asset_id)

    response = iso_client.delete(f"/api/v1/assets/{asset_id}", headers=headers)
    assert response.status_code == 204

    row = _asset_row(app, asset_id)
    assert row.status == "trashed"
    assert row.original_folder_id is not None
    assert ".trash" in row.file_path
    assert Path(row.file_path).is_file()
    assert not (managed_root / "objects" / str(asset_id)).exists()

    listing = iso_client.get("/api/v1/trash", headers=headers).json()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["id"] == asset_id
    assert item["original_folder"] == "回收甲"
    assert item["deleted_at"] is not None

    assets = iso_client.get("/api/v1/assets", params={"scope": "general"}, headers=headers).json()
    assert assets["total"] == 0


def test_restore_returns_file_to_objects_and_folder(iso_client, headers, app, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "回收乙")
    original_folder_id = _asset_row(app, asset_id).folder_id

    assert iso_client.delete(f"/api/v1/assets/{asset_id}", headers=headers).status_code == 204
    assert iso_client.post(f"/api/v1/trash/{asset_id}/restore", headers=headers).status_code == 204

    row = _asset_row(app, asset_id)
    assert row.status == "active"
    assert row.deleted_at is None
    assert row.folder_id == original_folder_id
    assert "objects" in row.file_path and ".trash" not in row.file_path
    assert Path(row.file_path).is_file()

    assets = iso_client.get("/api/v1/assets", params={"folder_id": original_folder_id}, headers=headers).json()
    assert assets["total"] == 1
    assert iso_client.get("/api/v1/trash", headers=headers).json()["total"] == 0


def test_permanent_delete_removes_file_and_row(iso_client, headers, app, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "回收丙")
    assert iso_client.delete(f"/api/v1/assets/{asset_id}", headers=headers).status_code == 204
    trash_path = Path(_asset_row(app, asset_id).file_path)
    assert trash_path.is_file()

    assert iso_client.delete(f"/api/v1/trash/{asset_id}", headers=headers).status_code == 204
    assert not trash_path.exists()
    assert _asset_row(app, asset_id) is None
    assert iso_client.get("/api/v1/trash", headers=headers).json()["total"] == 0

    content = iso_client.get(f"/api/v1/assets/{asset_id}/content", headers=headers)
    assert content.status_code == 404


def test_empty_trash_removes_everything(iso_client, headers, app, tmp_path) -> None:
    ids = make_assets(iso_client, headers, tmp_path, 2, "清空回收")
    for asset_id in ids:
        assert iso_client.delete(f"/api/v1/assets/{asset_id}", headers=headers).status_code == 204
    managed_root = _managed_root_of(app, ids[0])

    response = iso_client.post("/api/v1/trash/empty", headers=headers)
    assert response.status_code == 200
    assert response.json()["removed"] == 2
    assert response.json()["failed"] == 0

    assert iso_client.get("/api/v1/trash", headers=headers).json()["total"] == 0
    for asset_id in ids:
        assert _asset_row(app, asset_id) is None
    trash_root = managed_root / ".trash"
    assert not trash_root.exists() or list(trash_root.iterdir()) == []


def test_permanent_delete_locked_file_is_reported_not_lost(iso_client, headers, app, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "占用文件")
    assert iso_client.delete(f"/api/v1/assets/{asset_id}", headers=headers).status_code == 204
    trash_path = Path(_asset_row(app, asset_id).file_path)

    with open(trash_path, "rb"):  # hold a Windows handle so deletion must fail
        response = iso_client.delete(f"/api/v1/trash/{asset_id}", headers=headers)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "trash_delete_failed"
        assert _asset_row(app, asset_id) is not None, "record must survive a failed delete"

    assert iso_client.delete(f"/api/v1/trash/{asset_id}", headers=headers).status_code == 204
    assert _asset_row(app, asset_id) is None


def test_empty_trash_reports_partial_failure(iso_client, headers, app, tmp_path) -> None:
    free_id = _make_one(iso_client, headers, tmp_path, "部分清空甲")
    locked_id = _make_one(iso_client, headers, tmp_path, "部分清空乙")
    assert iso_client.delete(f"/api/v1/assets/{free_id}", headers=headers).status_code == 204
    assert iso_client.delete(f"/api/v1/assets/{locked_id}", headers=headers).status_code == 204
    locked_path = Path(_asset_row(app, locked_id).file_path)

    with open(locked_path, "rb"):
        response = iso_client.post("/api/v1/trash/empty", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["removed"] == 1 and body["failed"] == 1
        assert _asset_row(app, locked_id) is not None, "locked record survives"

    # handle released → a second empty clears the rest
    assert iso_client.post("/api/v1/trash/empty", headers=headers).json()["removed"] == 1


def test_delete_external_only_removes_index(iso_client, headers, app, tmp_path) -> None:
    asset_id, source = _make_external(app, tmp_path)

    response = iso_client.delete(f"/api/v1/assets/{asset_id}", headers=headers)
    assert response.status_code == 204

    assert source.is_file(), "external source file must never be touched"
    assert source.read_bytes() == b"external-source-bytes"
    assert _asset_row(app, asset_id) is None
    assert iso_client.get("/api/v1/trash", headers=headers).json()["total"] == 0


def test_bulk_trash_reports_per_item_results(iso_client, headers, app, tmp_path) -> None:
    good_id = _make_one(iso_client, headers, tmp_path, "批量删除甲")
    broken_id = _make_one(iso_client, headers, tmp_path, "批量删除乙")
    broken_row = _asset_row(app, broken_id)
    Path(broken_row.file_path).unlink()  # simulate a missing managed file

    response = iso_client.post("/api/v1/assets/bulk-trash", json={"asset_ids": [good_id, broken_id]}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ok_count"] == 1 and body["failed_count"] == 1
    by_id = {item["asset_id"]: item for item in body["items"]}
    assert by_id[good_id]["ok"] is True
    assert by_id[broken_id]["ok"] is False
    assert "回收站" in by_id[broken_id]["error"]

    assert _asset_row(app, good_id).status == "trashed"
    assert _asset_row(app, broken_id).status == "active"


def test_bulk_trash_includes_external_as_index_only(iso_client, headers, app, tmp_path) -> None:
    managed_id = _make_one(iso_client, headers, tmp_path, "批量删除混合")
    external_id, source = _make_external(app, tmp_path)

    response = iso_client.post(
        "/api/v1/assets/bulk-trash", json={"asset_ids": [managed_id, external_id]}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["ok_count"] == 2
    assert source.is_file()
    assert _asset_row(app, external_id) is None
    assert _asset_row(app, managed_id).status == "trashed"


def test_trash_endpoints_reject_missing_or_active(iso_client, headers, tmp_path) -> None:
    asset_id = _make_one(iso_client, headers, tmp_path, "异常路径")
    other_id = _make_one(iso_client, headers, tmp_path, "异常路径二")

    assert iso_client.delete("/api/v1/assets/99999", headers=headers).status_code == 404
    assert iso_client.get("/api/v1/trash", headers=headers).json()["total"] == 0

    # restoring / permanently deleting an asset that is not trashed → 404
    assert iso_client.post(f"/api/v1/trash/{asset_id}/restore", headers=headers).status_code == 404
    assert iso_client.delete(f"/api/v1/trash/{asset_id}", headers=headers).status_code == 404

    # double delete: the second time the row is gone → 404
    assert iso_client.delete(f"/api/v1/assets/{asset_id}", headers=headers).status_code == 204
    assert iso_client.delete(f"/api/v1/assets/{asset_id}", headers=headers).status_code == 404

    # restore flow still valid for the second asset
    assert iso_client.delete(f"/api/v1/assets/{other_id}", headers=headers).status_code == 204
    assert iso_client.post(f"/api/v1/trash/{other_id}/restore", headers=headers).status_code == 204


def test_bulk_trash_validation(iso_client, headers, tmp_path) -> None:
    empty = iso_client.post("/api/v1/assets/bulk-trash", json={"asset_ids": []}, headers=headers)
    assert empty.status_code == 422

    unknown = iso_client.post("/api/v1/assets/bulk-trash", json={"asset_ids": [424242]}, headers=headers)
    assert unknown.status_code == 404
