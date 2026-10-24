from __future__ import annotations

import time
from pathlib import Path

from backend.app.models.asset import Asset

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


def import_bytes(iso_client, headers, name: str, content: bytes, tmp_path) -> int:
    folder = iso_client.post(
        "/api/v1/folders", json={"name": f"内容-{name}", "scope": "general"}, headers=headers
    ).json()
    source = tmp_path / name
    source.write_bytes(content)
    job = iso_client.post(
        "/api/v1/imports", json={"paths": [str(source)], "folder_id": folder["id"]}, headers=headers
    ).json()
    final = wait_terminal(iso_client, headers, job["id"])
    assert final["status"] == "completed", final
    return final["items"][0]["asset_id"]


def test_content_serves_original_bytes(iso_client, headers, tmp_path) -> None:
    payload = b"content-endpoint-payload-\xe4\xbd\xa0\xe5\xa5\xbd"
    asset_id = import_bytes(iso_client, headers, "note.txt", payload, tmp_path)

    response = iso_client.get(f"/api/v1/assets/{asset_id}/content", headers=headers)
    assert response.status_code == 200
    assert response.content == payload
    assert "text/plain" in response.headers["content-type"]
    assert "note.txt" in response.headers.get("content-disposition", "")


def test_content_requires_token(iso_client) -> None:
    response = iso_client.get("/api/v1/assets/1/content", headers={"Host": "127.0.0.1"})
    assert response.status_code == 401


def test_content_missing_asset_404(iso_client, headers) -> None:
    response = iso_client.get("/api/v1/assets/9999/content", headers=headers)
    assert response.status_code == 404


def test_content_trashed_asset_404(iso_client, headers, app, tmp_path) -> None:
    asset_id = import_bytes(iso_client, headers, "trashed.bin", b"trash-me", tmp_path)
    with app.state.session_factory() as session:
        asset = session.get(Asset, asset_id)
        asset.status = "trashed"
        session.commit()

    response = iso_client.get(f"/api/v1/assets/{asset_id}/content", headers=headers)
    assert response.status_code == 404


def test_content_missing_file_404(iso_client, headers, app, tmp_path) -> None:
    asset_id = import_bytes(iso_client, headers, "vanish.bin", b"vanish-me", tmp_path)
    with app.state.session_factory() as session:
        asset = session.get(Asset, asset_id)
        path = asset.file_path
    Path(path).unlink()

    response = iso_client.get(f"/api/v1/assets/{asset_id}/content", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "content_unavailable"
