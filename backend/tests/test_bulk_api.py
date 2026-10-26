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


def make_assets(iso_client, headers, tmp_path, count: int, name: str) -> list[int]:
    folder = iso_client.post("/api/v1/folders", json={"name": name, "scope": "general"}, headers=headers).json()
    ids = []
    for index in range(count):
        source = tmp_path / f"{name}-{index}.txt"
        source.write_text(f"content {index}", encoding="utf-8")
        ids.append(import_one(iso_client, headers, folder["id"], source))
    return ids


def test_bulk_add_and_remove_tags(iso_client, headers, tmp_path) -> None:
    ids = make_assets(iso_client, headers, tmp_path, 3, "批量标签")
    tag_a = iso_client.post("/api/v1/tags", json={"name": "批量甲"}, headers=headers).json()
    tag_b = iso_client.post("/api/v1/tags", json={"name": "批量乙"}, headers=headers).json()

    result = iso_client.post(
        "/api/v1/assets/bulk-tags",
        json={"asset_ids": ids, "add_tag_ids": [tag_a["id"], tag_b["id"]]},
        headers=headers,
    )
    assert result.status_code == 200
    body = result.json()
    assert body["ok_count"] == 3 and body["failed_count"] == 0

    for asset_id in ids:
        assets = iso_client.get("/api/v1/assets", params={"scope": "general"}, headers=headers).json()
        item = [a for a in assets["items"] if a["id"] == asset_id][0]
        assert {t["name"] for t in item["tags"]} == {"批量甲", "批量乙"}

    remove = iso_client.post(
        "/api/v1/assets/bulk-tags",
        json={"asset_ids": ids, "remove_tag_ids": [tag_b["id"]]},
        headers=headers,
    )
    assert remove.json()["ok_count"] == 3

    both = iso_client.post(
        "/api/v1/assets/bulk-tags",
        json={"asset_ids": ids, "add_tag_ids": [tag_a["id"]], "remove_tag_ids": [tag_b["id"]]},
        headers=headers,
    )
    assert both.status_code == 422

    empty = iso_client.post("/api/v1/assets/bulk-tags", json={"asset_ids": ids}, headers=headers)
    assert empty.status_code == 422

    missing_asset = iso_client.post(
        "/api/v1/assets/bulk-tags",
        json={"asset_ids": [ids[0], 99999], "add_tag_ids": [tag_a["id"]]},
        headers=headers,
    )
    assert missing_asset.status_code == 404


def test_bulk_move_with_scope_guards(iso_client, headers, tmp_path) -> None:
    ids = make_assets(iso_client, headers, tmp_path, 2, "批量移动")
    target = iso_client.post("/api/v1/folders", json={"name": "目标目录", "scope": "general"}, headers=headers).json()

    result = iso_client.post(
        "/api/v1/assets/bulk-move",
        json={"asset_ids": ids, "target_folder_id": target["id"]},
        headers=headers,
    )
    assert result.status_code == 200
    assert result.json()["ok_count"] == 2

    assets = iso_client.get("/api/v1/assets", params={"folder_id": target["id"]}, headers=headers).json()
    assert assets["total"] == 2

    # moving into the same folder reports a per-item failure, not an error
    again = iso_client.post(
        "/api/v1/assets/bulk-move",
        json={"asset_ids": ids, "target_folder_id": target["id"]},
        headers=headers,
    ).json()
    assert again["ok_count"] == 0 and again["failed_count"] == 2

    # 跨项目与跨库移动现在得到允许
    project = iso_client.post("/api/v1/projects", json={"name": "批量项目"}, headers=headers).json()
    project_folder = iso_client.post(
        "/api/v1/folders", json={"name": "项目目录", "scope": "project", "project_id": project["id"]}, headers=headers
    ).json()
    cross = iso_client.post(
        "/api/v1/assets/bulk-move",
        json={"asset_ids": ids, "target_folder_id": project_folder["id"]},
        headers=headers,
    ).json()
    assert cross["ok_count"] == 2
    assert cross["failed_count"] == 0

    unknown_folder = iso_client.post(
        "/api/v1/assets/bulk-move",
        json={"asset_ids": ids, "target_folder_id": 99999},
        headers=headers,
    )
    assert unknown_folder.status_code == 404


def test_bulk_convert_to_managed(iso_client, headers, tmp_path) -> None:
    folder = iso_client.post("/api/v1/folders", json={"name": "外部转托管目录", "scope": "general"}, headers=headers).json()
    ext_dir = tmp_path / "ext_source"
    ext_dir.mkdir()
    f1 = ext_dir / "ext1.txt"
    f1.write_text("ext1 content", encoding="utf-8")
    f2 = ext_dir / "ext2.txt"
    f2.write_text("ext2 content", encoding="utf-8")

    iso_client.post(
        "/api/v1/external-sources",
        json={"root_path": str(ext_dir), "target_folder_id": folder["id"], "create_mount_folder": False},
        headers=headers,
    )

    assets = iso_client.get("/api/v1/assets", params={"folder_id": folder["id"]}, headers=headers).json()
    assert assets["total"] == 2
    ext_ids = [a["id"] for a in assets["items"]]
    assert all(a["source_type"] == "external" for a in assets["items"])

    managed_src = tmp_path / "managed.txt"
    managed_src.write_text("managed content", encoding="utf-8")
    managed_id = import_one(iso_client, headers, folder["id"], managed_src)

    all_ids = ext_ids + [managed_id]
    result = iso_client.post(
        "/api/v1/assets/bulk-convert-to-managed",
        json={"asset_ids": all_ids},
        headers=headers,
    )
    assert result.status_code == 200
    body = result.json()
    assert body["ok_count"] == 2
    assert body["failed_count"] == 1
    managed_res = next(item for item in body["items"] if item["asset_id"] == managed_id)
    assert managed_res["ok"] is False
    assert "无需转换" in managed_res["error"]

    updated_assets = iso_client.get("/api/v1/assets", params={"folder_id": folder["id"]}, headers=headers).json()
    converted_items = [a for a in updated_assets["items"] if a["id"] in ext_ids]
    assert all(a["source_type"] == "managed" for a in converted_items)
    assert f1.exists() and f2.exists()
