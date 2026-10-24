from __future__ import annotations

import os
import struct
import time
import zlib
from pathlib import Path

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def make_png(path: Path, size_bytes_target: int = 1024) -> Path:
    """Incompressible pixel data so the resulting file is ~size_bytes_target."""
    height = 8
    width = max(2, size_bytes_target // (3 * height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + os.urandom(3 * width) for _ in range(height))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return path


def make_text(path: Path, size_bytes_target: int, name_suffix: str = "") -> Path:
    payload = ("内容" + name_suffix) * (size_bytes_target // 6)
    path.write_text(payload[: size_bytes_target // 3], encoding="utf-8")
    return path


def wait_terminal(iso_client, headers, job_id: int) -> dict:
    for _ in range(300):
        last = iso_client.get(f"/api/v1/imports/{job_id}", headers=headers).json()
        if last["status"] in TERMINAL:
            assert last["status"] == "completed", last
            return last
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def seed(iso_client, headers, tmp_path) -> dict:
    """two folders; folder A gets images, folder B gets docs of varying sizes"""
    folder_a = iso_client.post("/api/v1/folders", json={"name": "角色图", "scope": "general"}, headers=headers).json()
    folder_b = iso_client.post("/api/v1/folders", json={"name": "场景素材", "scope": "general"}, headers=headers).json()
    child_b = iso_client.post(
        "/api/v1/folders", json={"name": "黄昏子集", "scope": "general", "parent_id": folder_b["id"]}, headers=headers
    ).json()

    paths = [
        (make_png(tmp_path / "hero-a.png", 1200), folder_a["id"]),
        (make_png(tmp_path / "hero-b.png", 24000), folder_a["id"]),
        (make_text(tmp_path / "场景说明.txt", 100), folder_b["id"]),
        (make_text(tmp_path / "黄昏参考.txt", 20000), child_b["id"]),
    ]
    job = iso_client.post(
        "/api/v1/imports", json={"paths": [str(p) for p, _ in paths], "folder_id": folder_a["id"]}, headers=headers
    ).json()
    wait_terminal(iso_client, headers, job["id"])
    # move last two into folder B via items? simpler: import separately per folder
    for path, folder_id in paths:
        job = iso_client.post(
            "/api/v1/imports", json={"paths": [str(path)], "folder_id": folder_id}, headers=headers
        ).json()
        wait_terminal(iso_client, headers, job["id"])
    return {"folder_a": folder_a, "folder_b": folder_b, "child_b": child_b}


def test_search_matches_name_and_folder_subtree(iso_client, headers, tmp_path) -> None:
    seed(iso_client, headers, tmp_path)

    by_name = iso_client.get("/api/v1/assets", params={"q": "hero-a", "scope": "general"}, headers=headers).json()
    assert by_name["total"] == 1
    assert by_name["items"][0]["name"] == "hero-a.png"

    # keyword "场景" matches folder 场景素材 and its child 黄昏子集? no — only exact subtree of matched folders
    by_folder = iso_client.get("/api/v1/assets", params={"q": "场景", "scope": "general"}, headers=headers).json()
    names = {item["name"] for item in by_folder["items"]}
    assert names == {"场景说明.txt"}

    by_child = iso_client.get("/api/v1/assets", params={"q": "黄昏", "scope": "general"}, headers=headers).json()
    assert {item["name"] for item in by_child["items"]} == {"黄昏参考.txt"}

    none = iso_client.get("/api/v1/assets", params={"q": "不存在关键词xyz", "scope": "general"}, headers=headers).json()
    assert none["total"] == 0


def test_type_and_size_filters(iso_client, headers, tmp_path) -> None:
    seed(iso_client, headers, tmp_path)

    images = iso_client.get("/api/v1/assets", params={"asset_type": "image", "scope": "general"}, headers=headers).json()
    assert images["total"] == 2
    documents = iso_client.get("/api/v1/assets", params={"asset_type": "document", "scope": "general"}, headers=headers).json()
    assert documents["total"] == 2

    small = iso_client.get(
        "/api/v1/assets", params={"size_max": 5000, "scope": "general"}, headers=headers
    ).json()
    assert {item["name"] for item in small["items"]} <= {"hero-a.png", "场景说明.txt"}

    big = iso_client.get(
        "/api/v1/assets", params={"size_min": 5000, "scope": "general"}, headers=headers
    ).json()
    assert {item["name"] for item in big["items"]} == {"hero-b.png", "黄昏参考.txt"}


def test_sort_orders(iso_client, headers, tmp_path) -> None:
    seed(iso_client, headers, tmp_path)

    by_name_asc = iso_client.get(
        "/api/v1/assets", params={"sort": "name", "order": "asc", "scope": "general"}, headers=headers
    ).json()
    names = [item["name"] for item in by_name_asc["items"]]
    assert names == sorted(names)

    by_size_desc = iso_client.get(
        "/api/v1/assets", params={"sort": "size", "order": "desc", "scope": "general"}, headers=headers
    ).json()
    sizes = [item["size_bytes"] for item in by_size_desc["items"]]
    assert sizes == sorted(sizes, reverse=True)

    by_created_asc = iso_client.get(
        "/api/v1/assets", params={"sort": "created_at", "order": "asc", "scope": "general"}, headers=headers
    ).json()
    ids = [item["id"] for item in by_created_asc["items"]]
    assert ids == sorted(ids)


def test_invalid_filters_rejected(iso_client, headers) -> None:
    bad_type = iso_client.get("/api/v1/assets", params={"asset_type": "hologram"}, headers=headers)
    assert bad_type.status_code == 422

    bad_sort = iso_client.get("/api/v1/assets", params={"sort": "magic"}, headers=headers)
    assert bad_sort.status_code == 422

    bad_date = iso_client.get("/api/v1/assets", params={"modified_after": "not-a-date"}, headers=headers)
    assert bad_date.status_code == 422
