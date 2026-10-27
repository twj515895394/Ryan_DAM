from __future__ import annotations

import time

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def _import_image(iso_client, headers, tmp_path, name: str, content: str = "image-bytes") -> int:
    folder = iso_client.post("/api/v1/folders", json={"name": f"{name}-目录", "scope": "general"}, headers=headers).json()
    source = tmp_path / name
    source.write_text(content, encoding="utf-8")
    job = iso_client.post("/api/v1/imports", json={"paths": [str(source)], "folder_id": folder["id"]}, headers=headers).json()
    for _ in range(300):
        final = iso_client.get(f"/api/v1/imports/{job['id']}", headers=headers).json()
        if final["status"] in TERMINAL:
            assert final["status"] == "completed", final
            break
        time.sleep(0.05)
    assets = iso_client.get("/api/v1/assets", params={"folder_id": folder["id"]}, headers=headers).json()
    return assets["items"][0]["id"]


MULTI_LINE_PROMPT = "masterpiece, best quality\na girl standing in rain --ar 2:3\n\n-negative: blurry, lowres\n保留中文与特殊字符 \"quotes\" <tags>"


def test_prompt_roundtrip_preserves_newlines(iso_client, headers, tmp_path) -> None:
    asset_id = _import_image(iso_client, headers, tmp_path, "prompt-hero.png")

    listing = iso_client.get("/api/v1/assets", params={"scope": "general"}, headers=headers).json()
    assert listing["items"][0]["has_prompt"] is False

    saved = iso_client.put(f"/api/v1/assets/{asset_id}/prompt", json={"prompt_text": MULTI_LINE_PROMPT}, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["has_prompt"] is True

    fetched = iso_client.get(f"/api/v1/assets/{asset_id}/prompt", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["prompt_text"] == MULTI_LINE_PROMPT, "must round-trip byte-exact"

    listing = iso_client.get("/api/v1/assets", params={"scope": "general"}, headers=headers).json()
    assert listing["items"][0]["has_prompt"] is True


def test_prompt_clear_and_overwrite(iso_client, headers, tmp_path) -> None:
    asset_id = _import_image(iso_client, headers, tmp_path, "prompt-clear.png")

    assert iso_client.put(f"/api/v1/assets/{asset_id}/prompt", json={"prompt_text": "第一版"}, headers=headers).status_code == 200
    overwritten = iso_client.put(f"/api/v1/assets/{asset_id}/prompt", json={"prompt_text": "第二版\n带换行"}, headers=headers)
    assert overwritten.json()["prompt_text"] == "第二版\n带换行"

    cleared = iso_client.put(f"/api/v1/assets/{asset_id}/prompt", json={"prompt_text": None}, headers=headers)
    assert cleared.json()["has_prompt"] is False
    assert cleared.json()["prompt_text"] is None

    empty = iso_client.put(f"/api/v1/assets/{asset_id}/prompt", json={"prompt_text": ""}, headers=headers)
    assert empty.json()["has_prompt"] is False


def test_prompt_only_for_image_and_video(iso_client, headers, tmp_path) -> None:
    folder = iso_client.post("/api/v1/folders", json={"name": "文档目录", "scope": "general"}, headers=headers).json()
    source = tmp_path / "note.txt"
    source.write_text("doc", encoding="utf-8")
    job = iso_client.post("/api/v1/imports", json={"paths": [str(source)], "folder_id": folder["id"]}, headers=headers).json()
    for _ in range(300):
        final = iso_client.get(f"/api/v1/imports/{job['id']}", headers=headers).json()
        if final["status"] in TERMINAL:
            break
        time.sleep(0.05)
    doc_id = iso_client.get("/api/v1/assets", params={"folder_id": folder["id"]}, headers=headers).json()["items"][0]["id"]

    rejected = iso_client.put(f"/api/v1/assets/{doc_id}/prompt", json={"prompt_text": "x"}, headers=headers)
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "unsupported_asset_type"

    fetched = iso_client.get(f"/api/v1/assets/{doc_id}/prompt", headers=headers)
    assert fetched.status_code == 422


def test_prompt_missing_asset(iso_client, headers) -> None:
    assert iso_client.get("/api/v1/assets/99999/prompt", headers=headers).status_code == 404
    assert iso_client.put("/api/v1/assets/99999/prompt", json={"prompt_text": "x"}, headers=headers).status_code == 404


def test_prompt_rejected_on_trashed_asset(iso_client, headers, tmp_path) -> None:
    asset_id = _import_image(iso_client, headers, tmp_path, "trashed-prompt.png")
    assert iso_client.delete(f"/api/v1/assets/{asset_id}", headers=headers).status_code == 204

    assert iso_client.get(f"/api/v1/assets/{asset_id}/prompt", headers=headers).status_code == 404
    rejected = iso_client.put(f"/api/v1/assets/{asset_id}/prompt", json={"prompt_text": "x"}, headers=headers)
    assert rejected.status_code == 404


def test_prompt_cas_conflict_handling(iso_client, headers, tmp_path) -> None:
    asset_id = _import_image(iso_client, headers, tmp_path, "cas-prompt.png")

    # 1. First write without CAS (initial revision is 1, becomes 2)
    p1 = iso_client.put(
        f"/api/v1/assets/{asset_id}/prompt",
        json={"prompt_text": "初始提示词", "prompt_origin": "manual"},
        headers=headers,
    )
    assert p1.status_code == 200
    assert p1.json()["prompt_revision"] == 2
    assert p1.json()["prompt_origin"] == "manual"

    # 2. Concurrent write with old expected_revision=1 must fail with 409 Conflict
    conflict = iso_client.put(
        f"/api/v1/assets/{asset_id}/prompt",
        json={
            "prompt_text": "被过期的修改",
            "expected_revision": 1,
            "prompt_origin": "ai_reverse",
        },
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "prompt_conflict"

    # Verify content was NOT modified
    current = iso_client.get(f"/api/v1/assets/{asset_id}/prompt", headers=headers).json()
    assert current["prompt_text"] == "初始提示词"
    assert current["prompt_revision"] == 2

    # 3. Write with correct expected_revision=2 succeeds and increments to 3
    success = iso_client.put(
        f"/api/v1/assets/{asset_id}/prompt",
        json={
            "prompt_text": "AI 反推成功更新",
            "expected_revision": 2,
            "prompt_origin": "ai_reverse",
        },
        headers=headers,
    )
    assert success.status_code == 200
    assert success.json()["prompt_text"] == "AI 反推成功更新"
    assert success.json()["prompt_origin"] == "ai_reverse"
    assert success.json()["prompt_revision"] == 3
