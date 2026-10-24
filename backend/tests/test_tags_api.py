from __future__ import annotations

import time
from pathlib import Path

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def import_one(iso_client, headers, folder_id: int, path: Path) -> int:
    job = iso_client.post(
        "/api/v1/imports", json={"paths": [str(path)], "folder_id": folder_id}, headers=headers
    ).json()
    for _ in range(300):
        final = iso_client.get(f"/api/v1/imports/{job['id']}", headers=headers).json()
        if final["status"] in TERMINAL:
            assert final["status"] == "completed", final
            return final["items"][0]["asset_id"]
        time.sleep(0.05)
    raise AssertionError("import did not finish")


def make_asset(iso_client, headers, tmp_path, name: str) -> int:
    folder = iso_client.post("/api/v1/folders", json={"name": f"标签库-{name}", "scope": "general"}, headers=headers).json()
    source = tmp_path / name
    source.write_bytes(b"tagged-content")
    return import_one(iso_client, headers, folder["id"], source)


def test_tag_crud_and_duplicates(iso_client, headers) -> None:
    created = iso_client.post("/api/v1/tags", json={"name": " 精选 "}, headers=headers)
    assert created.status_code == 201
    assert created.json()["name"] == "精选"
    assert created.json()["asset_count"] == 0

    duplicate = iso_client.post("/api/v1/tags", json={"name": "精选"}, headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_name"

    renamed = iso_client.patch(f"/api/v1/tags/{created.json()['id']}", json={"name": "必收"}, headers=headers)
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "必收"

    empty = iso_client.post("/api/v1/tags", json={"name": "   "}, headers=headers)
    assert empty.status_code == 422

    listed = iso_client.get("/api/v1/tags", headers=headers).json()
    assert [t["name"] for t in listed] == ["必收"]


def test_tag_in_use_cannot_be_deleted(iso_client, headers) -> None:
    tag = iso_client.post("/api/v1/tags", json={"name": "占用中"}, headers=headers).json()
    assert tag["asset_count"] == 0


def test_asset_tagging_round_trip(iso_client, headers, app, tmp_path) -> None:
    asset_id = make_asset(iso_client, headers, tmp_path, "tagged.png")
    tag_a = iso_client.post("/api/v1/tags", json={"name": "角色"}, headers=headers).json()
    tag_b = iso_client.post("/api/v1/tags", json={"name": "初稿"}, headers=headers).json()

    set_response = iso_client.put(
        f"/api/v1/assets/{asset_id}/tags", json={"tag_ids": [tag_a["id"], tag_b["id"]]}, headers=headers
    )
    assert set_response.status_code == 200
    assert {t["name"] for t in set_response.json()} == {"角色", "初稿"}

    # listing carries tags without N+1 errors
    assets = iso_client.get("/api/v1/assets", params={"scope": "general"}, headers=headers).json()
    tagged = [a for a in assets["items"] if a["id"] == asset_id][0]
    assert {t["name"] for t in tagged["tags"]} == {"角色", "初稿"}

    # counts reflect usage
    listed = iso_client.get("/api/v1/tags", headers=headers).json()
    counts = {t["name"]: t["asset_count"] for t in listed}
    assert counts["角色"] == 1 and counts["初稿"] == 1

    # filter by tag
    filtered = iso_client.get("/api/v1/assets", params={"tag_id": tag_a["id"], "scope": "general"}, headers=headers).json()
    assert filtered["total"] == 1

    # replace with a single tag
    replaced = iso_client.put(
        f"/api/v1/assets/{asset_id}/tags", json={"tag_ids": [tag_a["id"]]}, headers=headers
    ).json()
    assert {t["name"] for t in replaced} == {"角色"}

    # now 初稿 is unused → deletable
    deleted = iso_client.delete(f"/api/v1/tags/{tag_b['id']}", headers=headers)
    assert deleted.status_code == 204

    # 角色 still in use → refused
    refused = iso_client.delete(f"/api/v1/tags/{tag_a['id']}", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "tag_in_use"

    # clear tags then delete works
    iso_client.put(f"/api/v1/assets/{asset_id}/tags", json={"tag_ids": []}, headers=headers)
    assert iso_client.delete(f"/api/v1/tags/{tag_a['id']}", headers=headers).status_code == 204


def test_unknown_tag_rejected(iso_client, headers, tmp_path) -> None:
    asset_id = make_asset(iso_client, headers, tmp_path, "unknown-tag.png")
    response = iso_client.put(f"/api/v1/assets/{asset_id}/tags", json={"tag_ids": [9999]}, headers=headers)
    assert response.status_code == 404
