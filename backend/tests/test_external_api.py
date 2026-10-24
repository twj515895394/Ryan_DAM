from __future__ import annotations

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def _link(iso_client, headers, root, folder_id: int) -> dict:
    response = iso_client.post(
        "/api/v1/external-sources",
        json={"root_path": str(root), "target_folder_id": folder_id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _rescan(iso_client, headers, source_id: int) -> dict:
    response = iso_client.post(f"/api/v1/external-sources/{source_id}/scan", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _tree_names(iso_client, headers) -> set[str]:
    tree = iso_client.get("/api/v1/folders/tree?scope=general", headers=headers).json()
    names: set[str] = set()

    def walk(nodes):
        for node in nodes:
            names.add(node["name"])
            walk(node["children"])

    walk(tree)
    return names


def _assets_in(iso_client, headers, folder_id: int) -> list[dict]:
    return iso_client.get("/api/v1/assets", params={"folder_id": folder_id}, headers=headers).json()["items"]


def test_link_creates_index_without_touching_sources(iso_client, headers, tmp_path) -> None:
    root = tmp_path / "外部素材库"
    (root / "sub" / "deep").mkdir(parents=True)
    (root / "a.png").write_bytes(b"png-1")
    (root / "sub" / "b.txt").write_text("txt-2", encoding="utf-8")
    (root / "sub" / "deep" / "c.md").write_text("# md-3", encoding="utf-8")

    folder = iso_client.post("/api/v1/folders", json={"name": "外部目标", "scope": "general"}, headers=headers).json()
    body = _link(iso_client, headers, root, folder["id"])

    assert body["scan"] == {"added": 3, "updated": 0, "missing": 0, "reactivated": 0}
    source = body["source"]
    assert source["root_path"].lower() == str(root).lower()
    assert source["display_name"] == "外部素材库"
    assert source["target_folder_name"] == "外部目标"
    assert source["asset_count"] == 3
    assert source["missing_count"] == 0

    # hierarchy mirrored under the target folder; files indexed there
    assert {"sub", "deep"} <= _tree_names(iso_client, headers)
    top_names = {item["name"] for item in _assets_in(iso_client, headers, folder["id"])}
    assert top_names == {"a.png"}

    # every source file keeps its original bytes
    assert (root / "a.png").read_bytes() == b"png-1"
    assert (root / "sub" / "b.txt").read_text(encoding="utf-8") == "txt-2"
    assert (root / "sub" / "deep" / "c.md").read_text(encoding="utf-8") == "# md-3"

    listing = iso_client.get("/api/v1/external-sources", headers=headers).json()
    assert len(listing) == 1 and listing[0]["asset_count"] == 3


def test_rescan_idempotent_then_detects_changes_and_missing(iso_client, headers, tmp_path) -> None:
    root = tmp_path / "重扫库"
    root.mkdir()
    (root / "one.txt").write_text("v1", encoding="utf-8")
    (root / "two.txt").write_text("keep", encoding="utf-8")

    folder = iso_client.post("/api/v1/folders", json={"name": "重扫目标", "scope": "general"}, headers=headers).json()
    body = _link(iso_client, headers, root, folder["id"])
    source_id = body["source"]["id"]

    # idempotent: nothing changes
    assert _rescan(iso_client, headers, source_id) == {"added": 0, "updated": 0, "missing": 0, "reactivated": 0}

    # changed size + new file + deleted file
    (root / "one.txt").write_text("v1-with-longer-content", encoding="utf-8")
    (root / "three.txt").write_text("new", encoding="utf-8")
    (root / "two.txt").unlink()
    assert _rescan(iso_client, headers, source_id) == {"added": 1, "updated": 1, "missing": 1, "reactivated": 0}

    assets = iso_client.get("/api/v1/assets", params={"folder_id": folder["id"]}, headers=headers).json()
    by_name = {item["name"]: item for item in assets["items"]}
    assert by_name["two.txt"]["status"] == "missing", "vanished file must be flagged, not hidden"
    assert by_name["one.txt"]["size_bytes"] == len("v1-with-longer-content")

    # file comes back → reactivated
    (root / "two.txt").write_text("keep-restored", encoding="utf-8")
    assert _rescan(iso_client, headers, source_id)["reactivated"] == 1
    assets = iso_client.get("/api/v1/assets", params={"folder_id": folder["id"]}, headers=headers).json()
    by_name = {item["name"]: item for item in assets["items"]}
    assert by_name["two.txt"]["status"] == "active"


def test_missing_asset_content_reports_unavailable(iso_client, headers, tmp_path) -> None:
    root = tmp_path / "缺失库"
    root.mkdir()
    media = root / "song.mp3"
    media.write_bytes(b"audio-bytes")

    folder = iso_client.post("/api/v1/folders", json={"name": "缺失目标", "scope": "general"}, headers=headers).json()
    source_id = _link(iso_client, headers, root, folder["id"])["source"]["id"]

    assets = _assets_in(iso_client, headers, folder["id"])
    asset_id = assets[0]["id"]
    ok = iso_client.get(f"/api/v1/assets/{asset_id}/content", headers=headers)
    assert ok.status_code == 200

    media.unlink()
    _rescan(iso_client, headers, source_id)
    gone = iso_client.get(f"/api/v1/assets/{asset_id}/content", headers=headers)
    assert gone.status_code == 404
    assert gone.json()["error"]["code"] == "content_unavailable"
    assert "重新扫描" in gone.json()["error"]["message"]

    # the card stays visible in the listing
    assets = _assets_in(iso_client, headers, folder["id"])
    assert len(assets) == 1 and assets[0]["status"] == "missing"


def test_link_validation(iso_client, headers, tmp_path) -> None:
    missing_dir = iso_client.post(
        "/api/v1/external-sources",
        json={"root_path": str(tmp_path / "不存在"), "target_folder_id": 1},
        headers=headers,
    )
    assert missing_dir.status_code == 404
    assert missing_dir.json()["error"]["code"] == "source_unavailable"

    real_dir = tmp_path / "目录甲"
    real_dir.mkdir()
    (real_dir / "x.txt").write_text("x", encoding="utf-8")
    unknown_folder = iso_client.post(
        "/api/v1/external-sources",
        json={"root_path": str(real_dir), "target_folder_id": 999999},
        headers=headers,
    )
    assert unknown_folder.status_code == 404

    folder = iso_client.post("/api/v1/folders", json={"name": "校验目标", "scope": "general"}, headers=headers).json()
    _link(iso_client, headers, real_dir, folder["id"])
    duplicate = iso_client.post(
        "/api/v1/external-sources",
        json={"root_path": str(real_dir), "target_folder_id": folder["id"]},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_name"

    unknown_scan = iso_client.post("/api/v1/external-sources/424242/scan", headers=headers)
    assert unknown_scan.status_code == 404


def test_rescan_reports_unavailable_root(iso_client, headers, tmp_path) -> None:
    root = tmp_path / "消失库"
    root.mkdir()
    (root / "y.txt").write_text("y", encoding="utf-8")
    folder = iso_client.post("/api/v1/folders", json={"name": "消失目标", "scope": "general"}, headers=headers).json()
    source_id = _link(iso_client, headers, root, folder["id"])["source"]["id"]

    import shutil

    shutil.rmtree(root)
    response = iso_client.post(f"/api/v1/external-sources/{source_id}/scan", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "source_unavailable"

    # indexed rows stay intact (explicitly flagged only on a successful scan)
    assets = _assets_in(iso_client, headers, folder["id"])
    assert len(assets) == 1 and assets[0]["status"] == "active"
