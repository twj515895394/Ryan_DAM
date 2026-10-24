from __future__ import annotations

import os
import time
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from backend.app.models.asset import Asset
from backend.app.models.import_job import ImportJob

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def wait_terminal(client, headers, job_id: int, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/imports/{job_id}", headers=headers)
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] in TERMINAL:
            return last
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} did not finish: {last}")


def make_source(tmp_path: Path, name: str, content: bytes) -> Path:
    source = tmp_path / name
    source.write_bytes(content)
    return source


def import_paths(client, headers, folder_id: int, paths: list[str], **overrides) -> dict:
    payload = {"paths": paths, "folder_id": folder_id, **overrides}
    response = client.post("/api/v1/imports", json=payload, headers=headers)
    assert response.status_code == 202, response.text
    return response.json()


def create_general_folder(client, headers, name: str = "导入目录") -> int:
    response = client.post("/api/v1/folders", json={"name": name, "scope": "general"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_imports_require_token(client) -> None:
    response = client.post("/api/v1/imports", json={"paths": ["C:\\x.png"], "folder_id": 1}, headers={"Host": "127.0.0.1"})
    assert response.status_code == 401


def test_import_unknown_folder_rejected(client, headers, tmp_path) -> None:
    source = make_source(tmp_path, "a.png", b"png-bytes")
    response = client.post(
        "/api/v1/imports", json={"paths": [str(source)], "folder_id": 999}, headers=headers
    )
    assert response.status_code == 404


def test_empty_paths_rejected(client, headers) -> None:
    folder_id = create_general_folder(client, headers)
    response = client.post("/api/v1/imports", json={"paths": [], "folder_id": folder_id}, headers=headers)
    assert response.status_code == 422


def test_single_file_import_success(client, headers, app, tmp_path) -> None:
    folder_id = create_general_folder(client, headers)
    source = make_source(tmp_path, "hero.png", b"png-image-bytes-123")

    job = import_paths(client, headers, folder_id, [str(source)])
    final = wait_terminal(client, headers, job["id"])

    assert final["status"] == "completed", final
    assert final["success_count"] == 1
    assert final["failed_count"] == 0
    assert final["items"][0]["status"] == "success"

    session_factory: sessionmaker = app.state.session_factory
    with session_factory() as session:
        asset = session.query(Asset).one()
        assert asset.source_type == "managed"
        assert asset.name == "hero.png"
        assert asset.asset_type == "image"
        assert asset.sha256
        stored = Path(asset.file_path)
        assert stored.is_file(), stored
        assert stored.read_bytes() == b"png-image-bytes-123"
        assert f"objects{os.sep}{asset.id}" in str(stored)
        assert ".staging" not in str(stored)


def test_duplicate_content_skipped_by_default_then_forced(client, headers, tmp_path) -> None:
    folder_id = create_general_folder(client, headers)
    source = make_source(tmp_path, "same.bin", b"duplicate-content")

    first = import_paths(client, headers, folder_id, [str(source)])
    assert wait_terminal(client, headers, first["id"])["status"] == "completed"

    second = import_paths(client, headers, folder_id, [str(source)])
    second_final = wait_terminal(client, headers, second["id"])
    assert second_final["status"] == "completed"
    assert second_final["skipped_count"] == 1
    assert second_final["items"][0]["status"] == "skipped"
    assert "重复" in (second_final["items"][0]["error_message"] or "")

    forced = import_paths(client, headers, folder_id, [str(source)], allow_duplicates=True)
    forced_final = wait_terminal(client, headers, forced["id"])
    assert forced_final["status"] == "completed"
    assert forced_final["success_count"] == 1


def test_missing_source_fails_item_but_job_completes_others(client, headers, tmp_path) -> None:
    folder_id = create_general_folder(client, headers)
    good = make_source(tmp_path, "good.txt", b"good")
    missing = tmp_path / "missing.txt"

    job = import_paths(client, headers, folder_id, [str(missing), str(good)])
    final = wait_terminal(client, headers, job["id"])

    assert final["status"] == "completed_with_errors"
    assert final["success_count"] == 1
    assert final["failed_count"] == 1
    statuses = {item["status"] for item in final["items"]}
    assert statuses == {"success", "failed"}
    failed_item = next(i for i in final["items"] if i["status"] == "failed")
    assert "不存在" in failed_item["error_message"]


def test_insufficient_space_refuses_before_copy(client, headers, app, tmp_path, monkeypatch) -> None:
    folder_id = create_general_folder(client, headers)
    source = make_source(tmp_path, "big.bin", b"x" * 1024)

    class FakeUsage:
        def __init__(self) -> None:
            self.free = 0
            self.total = 0
            self.used = 0

    monkeypatch.setattr(import_service_module(), "disk_usage", lambda _probe: FakeUsage())

    response = client.post(
        "/api/v1/imports", json={"paths": [str(source)], "folder_id": folder_id}, headers=headers
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "insufficient_space"
    assert "空间不足" in body["error"]["message"]

    with app.state.session_factory() as session:
        assert session.query(Asset).count() == 0
        assert session.query(ImportJob).count() == 0
        assert source.is_file() and source.read_bytes() == b"x" * 1024


def import_service_module():
    import backend.app.services.import_service as module

    return module


def test_staging_cleaned_after_success(client, headers, app, tmp_path) -> None:
    folder_id = create_general_folder(client, headers)
    source = make_source(tmp_path, "cleanup.png", b"cleanup-bytes")

    job = import_paths(client, headers, folder_id, [str(source)])
    wait_terminal(client, headers, job["id"])

    with app.state.session_factory() as session:
        asset = session.query(Asset).one()
        managed_root = Path(asset.file_path).parents[2]
    staging_root = managed_root / ".staging"
    assert not staging_root.exists() or list(staging_root.iterdir()) == []
    assert (Path(asset.file_path)).is_file()


def test_relative_import_path_rejected(client, headers, tmp_path) -> None:
    folder_id = create_general_folder(client, headers)
    response = client.post(
        "/api/v1/imports", json={"paths": ["relative.png"], "folder_id": folder_id}, headers=headers
    )
    assert response.status_code == 422
