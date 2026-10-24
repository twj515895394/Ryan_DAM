from __future__ import annotations

import time

from backend.app.models.asset import Asset
from backend.app.models.folder import Folder

TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def make_tree(tmp_path):
    root = tmp_path / "source-lib"
    (root / "角色").mkdir(parents=True)
    (root / "角色" / "特写").mkdir(parents=True)
    (root / "场景").mkdir(parents=True)
    (root / "top.png").write_bytes(b"top")
    (root / "角色" / "a.png").write_bytes(b"char-a")
    (root / "角色" / "特写" / "b.bin").write_bytes(b"close-up")
    (root / "场景" / "a.png").write_bytes(b"scene-a")
    (root / "场景" / "notes.txt").write_bytes(b"notes")
    return root


def wait_terminal(client, headers, job_id: int, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        last = client.get(f"/api/v1/imports/{job_id}", headers=headers).json()
        if last["status"] in TERMINAL:
            return last
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {last}")


def test_folder_import_mirrors_hierarchy(client, headers, app, tmp_path) -> None:
    target = client.post("/api/v1/folders", json={"name": "素材", "scope": "general"}, headers=headers).json()
    source_root = make_tree(tmp_path)

    response = client.post(
        "/api/v1/imports/folder",
        json={"source_dir": str(source_root), "folder_id": target["id"]},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    final = wait_terminal(client, headers, response.json()["id"])

    assert final["status"] == "completed", final
    assert final["total_count"] == 5
    assert final["success_count"] == 5

    with app.state.session_factory() as session:
        folders = {f.name: f for f in session.query(Folder).all()}
        assert {"素材", "角色", "特写", "场景"} <= set(folders)
        # same file name in different subfolders both imported
        assert session.query(Asset).filter(Asset.name == "a.png").count() == 2
        closeup = session.query(Asset).filter(Asset.name == "b.bin").one()
        assert closeup.folder_id == folders["特写"].id
        top = session.query(Asset).filter(Asset.name == "top.png").one()
        assert top.folder_id == target["id"]
        notes = session.query(Asset).filter(Asset.name == "notes.txt").one()
        assert notes.asset_type == "document"

    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    target_node = next(n for n in tree if n["name"] == "素材")
    child_names = {c["name"] for c in target_node["children"]}
    assert child_names == {"角色", "场景"}


def test_folder_import_rerun_skips_duplicates(client, headers, tmp_path) -> None:
    target = client.post("/api/v1/folders", json={"name": "重复", "scope": "general"}, headers=headers).json()
    source_root = tmp_path / "dup-lib"
    (source_root / "sub").mkdir(parents=True)
    (source_root / "sub" / "x.png").write_bytes(b"same-x")

    first = client.post(
        "/api/v1/imports/folder", json={"source_dir": str(source_root), "folder_id": target["id"]}, headers=headers
    )
    assert wait_terminal(client, headers, first.json()["id"])["success_count"] == 1

    second = client.post(
        "/api/v1/imports/folder", json={"source_dir": str(source_root), "folder_id": target["id"]}, headers=headers
    )
    final = wait_terminal(client, headers, second.json()["id"])
    assert final["status"] == "completed"
    assert final["skipped_count"] == 1
    assert final["success_count"] == 0


def test_folder_import_requires_existing_dir(client, headers, tmp_path) -> None:
    target = client.post("/api/v1/folders", json={"name": "目标", "scope": "general"}, headers=headers).json()
    missing = client.post(
        "/api/v1/imports/folder",
        json={"source_dir": str(tmp_path / "nope"), "folder_id": target["id"]},
        headers=headers,
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "invalid_source"

    empty = tmp_path / "empty-lib"
    empty.mkdir()
    empty_response = client.post(
        "/api/v1/imports/folder", json={"source_dir": str(empty), "folder_id": target["id"]}, headers=headers
    )
    assert empty_response.status_code == 400

    unknown_folder = client.post(
        "/api/v1/imports/folder",
        json={"source_dir": str(tmp_path), "folder_id": 999},
        headers=headers,
    )
    assert unknown_folder.status_code == 404
