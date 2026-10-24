"""Media probing via bundled ffmpeg/ffprobe.

FFmpeg is a controlled bundle dependency: the locator checks, in order, the
RYAN_DAM_FFMPEG_DIR env var, the PyInstaller bundle (_MEIPASS/ffmpeg), the
repo ffmpeg-bin/ staging dir, and finally PATH. Placeholder files written by
scripts/prepare-ffmpeg.mjs are rejected by validating the "MZ" PE header, so
a missing bundle degrades gracefully (metadata/frames simply stay absent).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

FFMPEG_FRAME_SECONDS = 1.0
FFMPEG_TIMEOUT_SECONDS = 60


def _looks_like_exe(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < 4096:
            return False
        with path.open("rb") as handle:
            return handle.read(2) == b"MZ"
    except OSError:
        return False


def _candidates(binary: str) -> list[Path]:
    binary_name = f"{binary}.exe" if os.name == "nt" else binary
    found: list[Path] = []
    env_dir = os.environ.get("RYAN_DAM_FFMPEG_DIR")
    if env_dir:
        found.append(Path(env_dir) / binary_name)
    if getattr(sys, "frozen", False):
        found.append(Path(getattr(sys, "_MEIPASS", ".")) / "ffmpeg" / binary_name)
    found.append(Path(__file__).resolve().parents[3] / "ffmpeg-bin" / binary_name)
    return found


def _resolve(binary: str) -> str | None:
    for candidate in _candidates(binary):
        if _looks_like_exe(candidate):
            return str(candidate)
    located = _which(binary)
    return str(located) if located else None


def _which(binary: str) -> Path | None:
    from shutil import which

    result = which(binary)
    return Path(result) if result else None


def get_ffmpeg() -> str | None:
    return _resolve("ffmpeg")


def get_ffprobe() -> str | None:
    return _resolve("ffprobe")


def _run(command: list[str], timeout: int = FFMPEG_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        capture_output=True,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def probe(path: str) -> dict | None:
    """Return {duration_ms, width, height} when ffprobe can read the file."""
    ffprobe = get_ffprobe()
    if ffprobe is None:
        return None
    try:
        result = _run([
            ffprobe, "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", path,
        ])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout.decode("utf-8", errors="ignore"))
    except ValueError:
        return None
    media: dict = {}
    duration = payload.get("format", {}).get("duration")
    if duration is not None:
        try:
            media["duration_ms"] = int(round(float(duration) * 1000))
        except ValueError:
            pass
    has_video = False
    for stream in payload.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video" and stream.get("disposition", {}).get("attached_pic", 0) != 1:
            has_video = True
            try:
                media["width"] = int(stream["width"])
                media["height"] = int(stream["height"])
            except (KeyError, ValueError):
                pass
        elif codec_type == "audio" and "duration" not in media:
            stream_duration = stream.get("duration")
            if stream_duration is not None:
                try:
                    media["duration_ms"] = int(round(float(stream_duration) * 1000))
                except ValueError:
                    pass
    media["has_video_stream"] = has_video
    media["has_cover"] = any(
        stream.get("codec_type") == "video" and stream.get("disposition", {}).get("attached_pic", 0) == 1
        for stream in payload.get("streams", [])
    )
    return media


def extract_frame(path: str, destination: Path, *, max_size: int = 512) -> bool:
    """Grab a representative video frame scaled to fit max_size."""
    ffmpeg = get_ffmpeg()
    if ffmpeg is None:
        return False
    vf = f"scale=w={max_size}:h={max_size}:force_original_aspect_ratio=decrease"
    for seek in (f"-ss {FFMPEG_FRAME_SECONDS:g}", None):
        command = [ffmpeg, "-v", "quiet", "-y"]
        if seek:
            command += seek.split()
        command += ["-i", path, "-frames:v", "1", "-vf", vf, "-f", "image2", str(destination)]
        try:
            _run(command)
        except (OSError, subprocess.TimeoutExpired):
            return False
        if destination.exists() and destination.stat().st_size > 0:
            return True
    return False


def extract_cover(path: str, destination: Path) -> bool:
    """Extract embedded cover art from an audio file, if present."""
    ffprobe = get_ffprobe()
    if ffprobe is None:
        return False
    media = probe(path)
    if not media or not media.get("has_cover"):
        return False
    ffmpeg = get_ffmpeg()
    if ffmpeg is None:
        return False
    try:
        _run([
            ffmpeg, "-v", "quiet", "-y", "-i", path,
            "-map", "0:v:0", "-frames:v", "1", str(destination),
        ])
    except (OSError, subprocess.TimeoutExpired):
        return False
    return destination.exists() and destination.stat().st_size > 0
