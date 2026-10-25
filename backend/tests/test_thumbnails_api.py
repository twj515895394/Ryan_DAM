from __future__ import annotations

import io
import struct
import time
import zlib
from pathlib import Path

from PIL import Image

from backend.app.models.asset import Asset
from backend.app.services import thumbnail_service
from backend.app.services.settings_service import get_managed_root

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def make_png(path: Path, width: int, height: int, rgb=(120, 150, 200)) -> Path:
    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes(rgb) * width
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    )
    return path


def wait_terminal(iso_client, headers, job_id: int, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        last = iso_client.get(f"/api/v1/imports/{job_id}", headers=headers).json()
        if last["status"] in TERMINAL:
            return last
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {last}")


def import_image(iso_client, headers, tmp_path, name: str, width: int, height: int, rgb=(120, 150, 200)):
    folder = iso_client.post("/api/v1/folders", json={"name": f"图库-{name}", "scope": "general"}, headers=headers).json()
    source = make_png(tmp_path / name, width, height, rgb)
    job = iso_client.post(
        "/api/v1/imports", json={"paths": [str(source)], "folder_id": folder["id"]}, headers=headers
    ).json()
    final = wait_terminal(iso_client, headers, job["id"])
    assert final["status"] == "completed", final
    return final["items"][0]["asset_id"]


def wait_thumbnail_ready(app, asset_id: int, timeout: float = 15.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with app.state.session_factory() as session:
            asset = session.get(Asset, asset_id)
            if asset is not None and asset.thumbnail_status in {"ready", "failed"}:
                return asset.thumbnail_status
        time.sleep(0.1)
    raise AssertionError("thumbnail never reached a terminal status")


def test_thumbnail_generated_and_cache_hits(iso_client, headers, app, tmp_path) -> None:
    asset_id = import_image(iso_client, headers, tmp_path, "normal.png", 400, 300)
    assert wait_thumbnail_ready(app, asset_id) == "ready"

    response = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    first_bytes = response.content
    assert len(first_bytes) > 0
    with Image.open(io.BytesIO(first_bytes)) as thumb:
        assert max(thumb.size) <= 512

    thumb_file = thumbnail_service.thumbnail_file(asset_id)
    mtime_before = thumb_file.stat().st_mtime_ns
    second = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
    assert second.status_code == 200
    assert second.content == first_bytes
    assert thumb_file.stat().st_mtime_ns == mtime_before  # cache hit, no regeneration


def test_vertical_thumbnail_keeps_aspect(iso_client, headers, app, tmp_path) -> None:
    asset_id = import_image(iso_client, headers, tmp_path, "tall.png", 100, 400, (200, 120, 90))
    assert wait_thumbnail_ready(app, asset_id) == "ready"

    response = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
    with Image.open(io.BytesIO(response.content)) as thumb:
        width, height = thumb.size
    # PIL thumbnail() only downsizes: a 100x400 source stays 100x400, aspect intact.
    assert (width, height) == (100, 400)
    assert max(width, height) <= 512


def test_corrupt_image_marks_failed_and_falls_back(iso_client, headers, app, tmp_path) -> None:
    folder = iso_client.post("/api/v1/folders", json={"name": "损坏", "scope": "general"}, headers=headers).json()
    source = tmp_path / "broken.png"
    source.write_bytes(b"not-a-png-at-all")
    job = iso_client.post(
        "/api/v1/imports", json={"paths": [str(source)], "folder_id": folder["id"]}, headers=headers
    ).json()
    final = wait_terminal(iso_client, headers, job["id"])
    assert final["status"] == "completed"  # import itself must succeed
    asset_id = final["items"][0]["asset_id"]

    assert wait_thumbnail_ready(app, asset_id) == "failed"
    response = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "thumbnail_unavailable"


def test_source_change_regenerates_thumbnail(iso_client, headers, app, tmp_path) -> None:
    asset_id = import_image(iso_client, headers, tmp_path, "changing.png", 300, 200, (10, 120, 30))
    assert wait_thumbnail_ready(app, asset_id) == "ready"
    first = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers).content

    with app.state.session_factory() as session:
        asset = session.get(Asset, asset_id)
        source_path = Path(asset.file_path)
        managed_root = Path(get_managed_root(session))
    make_png(source_path, 500, 480, (250, 80, 40))
    assert str(managed_root) in str(source_path)  # asset lives under the managed root

    # Changed source: fingerprint mismatch → regeneration is re-enqueued on request.
    deadline = time.monotonic() + 15
    second = None
    while time.monotonic() < deadline:
        second = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
        if second.status_code == 200:
            break
        time.sleep(0.1)
    assert second is not None and second.status_code == 200
    assert second.content != first


def test_non_image_asset_returns_404(iso_client, headers, app, tmp_path) -> None:
    folder = iso_client.post("/api/v1/folders", json={"name": "文本", "scope": "general"}, headers=headers).json()
    source = tmp_path / "note.txt"
    source.write_text("hello", encoding="utf-8")
    job = iso_client.post(
        "/api/v1/imports", json={"paths": [str(source)], "folder_id": folder["id"]}, headers=headers
    ).json()
    final = wait_terminal(iso_client, headers, job["id"])
    asset_id = final["items"][0]["asset_id"]

    response = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
    assert response.status_code == 404


def test_thumbnail_requires_token(iso_client) -> None:
    response = iso_client.get("/api/v1/assets/1/thumbnail", headers={"Host": "127.0.0.1"})
    assert response.status_code == 401


def test_trashed_asset_thumbnail_accessible(iso_client, headers, app, tmp_path) -> None:
    asset_id = import_image(iso_client, headers, tmp_path, "will_trash.png", 200, 200)
    assert wait_thumbnail_ready(app, asset_id) == "ready"

    # Move to trash
    del_res = iso_client.delete(f"/api/v1/assets/{asset_id}", headers=headers)
    assert del_res.status_code == 204

    # Thumbnail should still be accessible for previewing in trash
    response = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"

