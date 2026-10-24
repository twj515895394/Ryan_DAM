from __future__ import annotations

import time

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


def test_unlink_removes_only_external_index(iso_client, headers, app, tmp_path) -> None:
    from sqlalchemy.orm import sessionmaker

    from backend.app.models.asset import Asset

    root = tmp_path / "解除库"
    root.mkdir()
    (root / "keep.txt").write_text("source-keep", encoding="utf-8")
    (root / "gone.txt").write_text("source-gone", encoding="utf-8")

    folder = iso_client.post("/api/v1/folders", json={"name": "解除目标", "scope": "general"}, headers=headers).json()
    source_id = _link(iso_client, headers, root, folder["id"])["source"]["id"]

    # simulate ticket 19's conversion: flip one row to managed in place
    session_factory: sessionmaker = app.state.session_factory
    with session_factory() as session:
        rows = session.query(Asset).order_by(Asset.name).all()
        converted = next(row for row in rows if row.name == "keep.txt")
        still_external = next(row for row in rows if row.name == "gone.txt")
        converted.source_type = "managed"
        converted.external_source_id = None
        converted_id = converted.id
        still_external_id = still_external.id
        session.commit()

    response = iso_client.delete(f"/api/v1/external-sources/{source_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["removed"] == 1, "only the still-external index row goes away"

    with session_factory() as session:
        kept = session.get(Asset, converted_id)
        assert kept is not None, "converted asset must survive the unlink"
        assert kept.source_type == "managed"
        assert session.get(Asset, still_external_id) is None

    # source files untouched on disk
    assert (root / "keep.txt").read_text(encoding="utf-8") == "source-keep"
    assert (root / "gone.txt").read_text(encoding="utf-8") == "source-gone"

    # the source record is gone
    listing = iso_client.get("/api/v1/external-sources", headers=headers).json()
    assert listing == []

    # the converted asset is still browsable in the target folder
    assets = _assets_in(iso_client, headers, folder["id"])
    assert [item["name"] for item in assets] == ["keep.txt"]
    assert assets[0]["source_type"] == "managed"

    # second unlink of the same source → 404
    again = iso_client.delete(f"/api/v1/external-sources/{source_id}", headers=headers)
    assert again.status_code == 404


def test_convert_to_managed_updates_record_in_place(iso_client, headers, app, tmp_path) -> None:
    from pathlib import Path

    from sqlalchemy.orm import sessionmaker

    from backend.app.models.asset import Asset

    root = tmp_path / "转托管库"
    root.mkdir()
    media = root / "hero.png"
    media.write_bytes(b"convertible-image-bytes")

    folder = iso_client.post("/api/v1/folders", json={"name": "转托管目标", "scope": "general"}, headers=headers).json()
    source_id = _link(iso_client, headers, root, folder["id"])["source"]["id"]

    assets = _assets_in(iso_client, headers, folder["id"])
    asset_id = assets[0]["id"]
    # give it a tag to verify metadata survives
    tag = iso_client.post("/api/v1/tags", json={"name": "转托管标签"}, headers=headers).json()
    assert iso_client.put(f"/api/v1/assets/{asset_id}/tags", json={"tag_ids": [tag["id"]]}, headers=headers).status_code == 200

    response = iso_client.post(f"/api/v1/assets/{asset_id}/convert-to-managed", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_type"] == "managed"
    assert body["id"] == asset_id, "same record, no second card"
    assert body["folder_id"] == folder["id"]
    assert [t["name"] for t in body["tags"]] == ["转托管标签"]
    assert "objects" in body["file_path"], "managed copy lives under objects/"
    assert "转托管库" not in body["file_path"], "copy must leave the external source dir"

    session_factory: sessionmaker = app.state.session_factory
    with session_factory() as session:
        row = session.get(Asset, asset_id)
        assert row.source_type == "managed"
        assert row.external_source_id is None
        assert row.sha256 is not None
        assert Path(row.file_path).is_file()
        managed_path = Path(row.file_path)

    assert media.is_file(), "source file must stay on disk"
    assert media.read_bytes() == b"convertible-image-bytes"
    assert managed_path.read_bytes() == b"convertible-image-bytes"

    # exactly one asset remains in the library
    total = iso_client.get("/api/v1/assets", params={"folder_id": folder["id"]}, headers=headers).json()["total"]
    assert total == 1

    # the source record is gone; unlink would now only remove nothing extra
    assert iso_client.get("/api/v1/external-sources", headers=headers).json()[0]["asset_count"] == 0
    # rescan would re-add the still-present source file as a new external index
    scan = _rescan(iso_client, headers, source_id)
    assert scan["added"] == 1, "source file still exists so it gets re-indexed"
    with session_factory() as session:
        session.expire_all()
        row = session.get(Asset, asset_id)
        assert row.source_type == "managed", "rescan must not touch the converted record"


def test_convert_failure_keeps_external(iso_client, headers, app, tmp_path) -> None:
    from sqlalchemy.orm import sessionmaker

    from backend.app.models.asset import Asset

    root = tmp_path / "转托管失败库"
    root.mkdir()
    media = root / "ghost.txt"
    media.write_text("gone-soon", encoding="utf-8")
    folder = iso_client.post("/api/v1/folders", json={"name": "失败目标", "scope": "general"}, headers=headers).json()
    _link(iso_client, headers, root, folder["id"])
    asset_id = _assets_in(iso_client, headers, folder["id"])[0]["id"]

    media.unlink()  # file vanishes without a rescan: row still says active/external
    response = iso_client.post(f"/api/v1/assets/{asset_id}/convert-to-managed", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "content_unavailable"

    session_factory: sessionmaker = app.state.session_factory
    with session_factory() as session:
        row = session.get(Asset, asset_id)
        assert row.source_type == "external"
    assets = _assets_in(iso_client, headers, folder["id"])
    assert assets[0]["source_type"] == "external", "failure keeps the asset external and retryable"


def test_convert_rejects_managed_and_insufficient_space(iso_client, headers, app, tmp_path, monkeypatch) -> None:
    import backend.app.services.external_service as external_module

    root = tmp_path / "空间库"
    root.mkdir()
    (root / "big.bin").write_bytes(b"x" * 2048)
    folder = iso_client.post("/api/v1/folders", json={"name": "空间目标", "scope": "general"}, headers=headers).json()
    _link(iso_client, headers, root, folder["id"])
    asset_id = _assets_in(iso_client, headers, folder["id"])[0]["id"]

    class FakeUsage:
        free = 0
        total = 1
        used = 1

    monkeypatch.setattr(external_module.shutil, "disk_usage", lambda _p: FakeUsage())
    response = iso_client.post(f"/api/v1/assets/{asset_id}/convert-to-managed", headers=headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "insufficient_space"
    assert _assets_in(iso_client, headers, folder["id"])[0]["source_type"] == "external"

    monkeypatch.setattr(external_module.shutil, "disk_usage", lambda _p: None, raising=False)
    # convert a managed import instead → rejected
    source = tmp_path / "managed.txt"
    source.write_text("managed", encoding="utf-8")
    job = iso_client.post("/api/v1/imports", json={"paths": [str(source)], "folder_id": folder["id"]}, headers=headers).json()
    for _ in range(300):
        final = iso_client.get(f"/api/v1/imports/{job['id']}", headers=headers).json()
        if final["status"] in {"completed", "failed"}:
            break
    managed_id = final["items"][0]["asset_id"]
    rejected = iso_client.post(f"/api/v1/assets/{managed_id}/convert-to-managed", headers=headers)
    assert rejected.status_code == 422


def test_convert_rejected_on_trashed_asset(iso_client, headers, app, tmp_path) -> None:
    from sqlalchemy.orm import sessionmaker

    from backend.app.models.asset import Asset

    root = tmp_path / "转托管回收库"
    root.mkdir()
    (root / "doomed.txt").write_text("doomed", encoding="utf-8")
    folder = iso_client.post("/api/v1/folders", json={"name": "回收转换目标", "scope": "general"}, headers=headers).json()
    _link(iso_client, headers, root, folder["id"])
    asset_id = _assets_in(iso_client, headers, folder["id"])[0]["id"]

    # external deletion is index-only, so convert an imported managed file instead
    seed = tmp_path / "doomed-managed.txt"
    seed.write_text("doomed-managed", encoding="utf-8")
    job = iso_client.post("/api/v1/imports", json={"paths": [str(seed)], "folder_id": folder["id"]}, headers=headers).json()
    for _ in range(300):
        final = iso_client.get(f"/api/v1/imports/{job['id']}", headers=headers).json()
        if final["status"] in TERMINAL:
            break
        time.sleep(0.05)
    managed_id = final["items"][0]["asset_id"]
    assert iso_client.delete(f"/api/v1/assets/{managed_id}", headers=headers).status_code == 204

    session_factory: sessionmaker = app.state.session_factory
    with session_factory() as session:
        row = session.get(Asset, managed_id)
        assert row is not None and row.status == "trashed"

    response = iso_client.post(f"/api/v1/assets/{managed_id}/convert-to-managed", headers=headers)
    assert response.status_code == 404


def test_scan_skips_managed_root_subtree(iso_client, headers, tmp_path) -> None:
    """把托管根的父目录关联为外部源时，不得把 objects/.trash/.staging 索引进来。"""
    parent = tmp_path / "hosting"
    managed = parent / "managed-assets"
    managed.mkdir(parents=True)
    (parent / "outside.txt").write_text("outside", encoding="utf-8")

    # point the app's managed root at parent/managed-assets
    assert iso_client.patch(
        "/api/v1/settings",
        json={"managed_root": str(managed)},
        headers=headers,
    ).status_code == 200

    folder = iso_client.post("/api/v1/folders", json={"name": "父目录关联", "scope": "general"}, headers=headers).json()
    source_id = _link(iso_client, headers, parent, folder["id"])["source"]["id"]

    # seed a managed import into the managed root, then rescan the external source
    seed = tmp_path / "managed-seed.txt"
    seed.write_text("managed-content", encoding="utf-8")
    job = iso_client.post("/api/v1/imports", json={"paths": [str(seed)], "folder_id": folder["id"]}, headers=headers).json()
    for _ in range(300):
        final = iso_client.get(f"/api/v1/imports/{job['id']}", headers=headers).json()
        if final["status"] in TERMINAL:
            break
        time.sleep(0.05)

    scan = _rescan(iso_client, headers, source_id)
    assert scan["added"] == 0, "managed storage files must never be re-indexed"

    items = _assets_in(iso_client, headers, folder["id"])
    external_names = {item["name"] for item in items if item["source_type"] == "external"}
    assert external_names == {"outside.txt"}
    external_paths = [item["file_path"] for item in items if item["source_type"] == "external"]
    assert all("managed-assets" not in path for path in external_paths)
