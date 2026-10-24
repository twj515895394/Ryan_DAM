from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from backend.app.models.asset import Asset
from backend.app.services import media_service
from backend.app.services.settings_service import get_managed_root

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}

HAS_FFMPEG = media_service.get_ffmpeg() is not None and media_service.get_ffprobe() is not None


def wait_terminal(iso_client, headers, job_id: int, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        last = iso_client.get(f"/api/v1/imports/{job_id}", headers=headers).json()
        if last["status"] in TERMINAL:
            return last
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {last}")


def wait_thumbnail_status(app, asset_id: int, status: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with app.state.session_factory() as session:
            asset = session.get(Asset, asset_id)
            if asset is not None and asset.thumbnail_status == status:
                return
        time.sleep(0.1)
    raise AssertionError(f"thumbnail never reached {status}")


def run_ffmpeg(*args: str) -> None:
    ffmpeg = media_service.get_ffmpeg()
    assert ffmpeg is not None
    result = subprocess.run(
        [ffmpeg, "-v", "quiet", "-y", *args],
        capture_output=True,
        timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if media_service.os.name == "nt" else 0,
    )
    assert result.returncode == 0, result.stderr[-500:]


def import_one(iso_client, headers, folder_id: int, path: Path) -> dict:
    job = iso_client.post(
        "/api/v1/imports", json={"paths": [str(path)], "folder_id": folder_id}, headers=headers
    ).json()
    return wait_terminal(iso_client, headers, job["id"])


def create_folder(iso_client, headers, name: str) -> int:
    response = iso_client.post("/api/v1/folders", json={"name": name, "scope": "general"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not available in this environment")
def test_video_metadata_and_frame(iso_client, headers, app, tmp_path) -> None:
    folder_id = create_folder(iso_client, headers, "视频")
    video = tmp_path / "clip.mp4"
    run_ffmpeg(
        "-f", "lavfi", "-i", "testsrc=duration=1:size=128x96:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(video),
    )
    final = import_one(iso_client, headers, folder_id, video)
    asset_id = final["items"][0]["asset_id"]

    wait_thumbnail_status(app, asset_id, "ready")
    with app.state.session_factory() as session:
        asset = session.get(Asset, asset_id)
        assert asset.media_duration_ms is not None
        assert abs(asset.media_duration_ms - 1000) <= 500
        assert asset.media_width == 128
        assert asset.media_height == 96

    response = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 0


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not available in this environment")
def test_audio_duration_without_cover(iso_client, headers, app, tmp_path) -> None:
    folder_id = create_folder(iso_client, headers, "音频")
    audio = tmp_path / "tone.mp3"
    run_ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "libmp3lame", str(audio))
    final = import_one(iso_client, headers, folder_id, audio)
    asset_id = final["items"][0]["asset_id"]

    wait_thumbnail_status(app, asset_id, "ready")
    with app.state.session_factory() as session:
        asset = session.get(Asset, asset_id)
        assert asset.media_duration_ms is not None
        assert abs(asset.media_duration_ms - 1000) <= 500

    response = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
    assert response.status_code == 404  # no embedded cover → type icon fallback


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not available in this environment")
def test_audio_with_cover_gets_thumbnail(iso_client, headers, app, tmp_path) -> None:
    folder_id = create_folder(iso_client, headers, "有声封面")
    cover = tmp_path / "cover.png"
    audio = tmp_path / "song.mp3"
    run_ffmpeg("-f", "lavfi", "-i", "color=c=blue:size=64x64:duration=0.1", "-frames:v", "1", str(cover))
    run_ffmpeg(
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-i", str(cover),
        "-map", "0:a", "-map", "1:v",
        "-c:a", "libmp3lame", "-c:v", "mjpeg",
        "-disposition:v", "attached_pic", str(audio),
    )
    final = import_one(iso_client, headers, folder_id, audio)
    asset_id = final["items"][0]["asset_id"]

    wait_thumbnail_status(app, asset_id, "ready")
    response = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not available in this environment")
def test_corrupt_video_falls_back_without_breaking_import(iso_client, headers, app, tmp_path) -> None:
    folder_id = create_folder(iso_client, headers, "损坏视频")
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"garbage-not-a-video")
    final = import_one(iso_client, headers, folder_id, broken)
    assert final["status"] == "completed"
    asset_id = final["items"][0]["asset_id"]

    wait_thumbnail_status(app, asset_id, "failed")
    response = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
    assert response.status_code == 404
    with app.state.session_factory() as session:
        asset = session.get(Asset, asset_id)
        assert Path(asset.file_path).is_file()  # source file untouched


def test_missing_ffmpeg_marks_failed(iso_client, headers, app, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(media_service, "get_ffprobe", lambda: None)
    monkeypatch.setattr(media_service, "get_ffmpeg", lambda: None)

    folder_id = create_folder(iso_client, headers, "无ffmpeg")
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake-video-bytes")
    final = import_one(iso_client, headers, folder_id, source)
    asset_id = final["items"][0]["asset_id"]

    wait_thumbnail_status(app, asset_id, "failed")
    response = iso_client.get(f"/api/v1/assets/{asset_id}/thumbnail", headers=headers)
    assert response.status_code == 404


def test_ffmpeg_locator_rejects_placeholders(monkeypatch, tmp_path) -> None:
    (tmp_path / "ffmpeg.exe").write_text("PLACEHOLDER - not a real binary\n")
    monkeypatch.setenv("RYAN_DAM_FFMPEG_DIR", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert media_service.get_ffmpeg() is None
    assert media_service.get_ffprobe() is None


def test_placeholder_never_shipped_real_check() -> None:
    """Real exes pass the MZ check; text placeholders never do."""
    assert media_service._looks_like_exe(Path("definitely-missing.exe")) is False
