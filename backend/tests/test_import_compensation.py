from __future__ import annotations

import time
from pathlib import Path

from backend.app.models.asset import Asset
from backend.app.services.settings_service import get_managed_root

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def wait_terminal(iso_client, headers, job_id: int, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        last = iso_client.get(f"/api/v1/imports/{job_id}", headers=headers).json()
        if last["status"] in TERMINAL:
            return last
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {last}")


def import_service_module():
    import backend.app.services.import_service as module

    return module


def test_directory_path_rejected_for_file_import(iso_client, headers, tmp_path) -> None:
    folder = iso_client.post("/api/v1/folders", json={"name": "目录", "scope": "general"}, headers=headers).json()
    response = iso_client.post(
        "/api/v1/imports", json={"paths": [str(tmp_path)], "folder_id": folder["id"]}, headers=headers
    )
    assert response.status_code == 422
    assert "导入文件夹" in response.json()["error"]["message"]


def test_move_failure_cleans_staged_and_partial_files(iso_client, headers, app, tmp_path, monkeypatch) -> None:
    folder = iso_client.post("/api/v1/folders", json={"name": "补偿", "scope": "general"}, headers=headers).json()
    source = tmp_path / "doomed.png"
    source.write_bytes(b"doomed-bytes")

    def fake_move(src, dst):
        Path(dst).write_bytes(b"partial")  # simulate a half-written destination
        raise OSError("disk full")

    monkeypatch.setattr(import_service_module(), "_atomic_move", fake_move)

    job = iso_client.post(
        "/api/v1/imports", json={"paths": [str(source)], "folder_id": folder["id"]}, headers=headers
    ).json()
    final = wait_terminal(iso_client, headers, job["id"])

    assert final["status"] == "failed"
    assert final["failed_count"] == 1
    assert "导入失败" in (final["items"][0]["error_message"] or "")

    with app.state.session_factory() as session:
        assert session.query(Asset).count() == 0
        managed_root = Path(get_managed_root(session))

    objects_dir = managed_root / "objects"
    assert not objects_dir.exists() or list(objects_dir.iterdir()) == []
    staging_root = managed_root / ".staging"
    assert not staging_root.exists() or all(
        not any(d.iterdir()) for d in staging_root.iterdir() if d.is_dir()
    )
    assert source.is_file() and source.read_bytes() == b"doomed-bytes"
