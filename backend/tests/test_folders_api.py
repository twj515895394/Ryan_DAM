from __future__ import annotations


def _create(client, headers, payload):
    response = client.post("/api/v1/folders", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_general_folder_tree_nesting(client, headers) -> None:
    parent = _create(client, headers, {"name": "角色图", "scope": "general"})
    child = _create(client, headers, {"name": "主角", "scope": "general", "parent_id": parent["id"]})

    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert len(tree) == 1
    assert tree[0]["name"] == "角色图"
    assert [c["name"] for c in tree[0]["children"]] == ["主角"]
    assert child["parent_id"] == parent["id"]


def test_project_folders_are_isolated(client, headers) -> None:
    alpha = client.post("/api/v1/projects", json={"name": "Alpha"}, headers=headers).json()
    beta = client.post("/api/v1/projects", json={"name": "Beta"}, headers=headers).json()
    _create(client, headers, {"name": "Alpha 场景", "scope": "project", "project_id": alpha["id"]})
    _create(client, headers, {"name": "Beta 场景", "scope": "project", "project_id": beta["id"]})

    alpha_tree = client.get(
        "/api/v1/folders/tree", params={"scope": "project", "project_id": alpha["id"]}, headers=headers
    ).json()
    beta_tree = client.get(
        "/api/v1/folders/tree", params={"scope": "project", "project_id": beta["id"]}, headers=headers
    ).json()
    assert [n["name"] for n in alpha_tree] == ["Alpha 场景"]
    assert [n["name"] for n in beta_tree] == ["Beta 场景"]

    general_tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert general_tree == []


def test_duplicate_sibling_name_rejected_but_allowed_in_other_branch(client, headers) -> None:
    parent = _create(client, headers, {"name": "素材", "scope": "general"})
    other = _create(client, headers, {"name": "其他", "scope": "general"})
    _create(client, headers, {"name": "参考", "scope": "general", "parent_id": parent["id"]})

    duplicate = client.post(
        "/api/v1/folders", json={"name": "参考", "scope": "general", "parent_id": parent["id"]}, headers=headers
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_name"

    allowed = client.post(
        "/api/v1/folders", json={"name": "参考", "scope": "general", "parent_id": other["id"]}, headers=headers
    )
    assert allowed.status_code == 201


def test_invalid_folder_name_rejected(client, headers) -> None:
    for bad in ["a/b", "a\\b", "<x>", ".."]:
        response = client.post("/api/v1/folders", json={"name": bad, "scope": "general"}, headers=headers)
        assert response.status_code == 422, bad


def test_move_folder_and_reject_cycles(client, headers) -> None:
    top = _create(client, headers, {"name": "顶层", "scope": "general"})
    mid = _create(client, headers, {"name": "中层", "scope": "general", "parent_id": top["id"]})
    leaf = _create(client, headers, {"name": "叶子", "scope": "general", "parent_id": mid["id"]})

    moved = client.patch(f"/api/v1/folders/{leaf['id']}", json={"parent_id": None}, headers=headers)
    assert moved.status_code == 200
    assert moved.json()["parent_id"] is None

    cycle = client.patch(f"/api/v1/folders/{top['id']}", json={"parent_id": mid["id"]}, headers=headers)
    assert cycle.status_code == 400
    assert cycle.json()["error"]["code"] == "invalid_move"

    self_move = client.patch(f"/api/v1/folders/{top['id']}", json={"parent_id": top["id"]}, headers=headers)
    assert self_move.status_code == 400


def test_cross_scope_and_cross_project_moves_rejected(client, headers) -> None:
    project = client.post("/api/v1/projects", json={"name": "P1"}, headers=headers).json()
    project2 = client.post("/api/v1/projects", json={"name": "P2"}, headers=headers).json()
    general_folder = _create(client, headers, {"name": "通用", "scope": "general"})
    project_folder = _create(client, headers, {"name": "项目", "scope": "project", "project_id": project["id"]})
    other_project_folder = _create(
        client, headers, {"name": "其他项目", "scope": "project", "project_id": project2["id"]}
    )

    into_project = client.patch(
        f"/api/v1/folders/{general_folder['id']}", json={"parent_id": project_folder["id"]}, headers=headers
    )
    assert into_project.status_code == 400
    assert into_project.json()["error"]["code"] == "invalid_parent"

    cross_project = client.patch(
        f"/api/v1/folders/{other_project_folder['id']}", json={"parent_id": project_folder["id"]}, headers=headers
    )
    assert cross_project.status_code == 400


def test_rename_folder_conflicts_within_same_parent(client, headers) -> None:
    first = _create(client, headers, {"name": "A", "scope": "general"})
    second = _create(client, headers, {"name": "B", "scope": "general"})

    conflict = client.patch(f"/api/v1/folders/{second['id']}", json={"name": "A"}, headers=headers)
    assert conflict.status_code == 409

    renamed = client.patch(f"/api/v1/folders/{second['id']}", json={"name": "B2"}, headers=headers)
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "B2"


def test_delete_folder_protection(client, headers) -> None:
    parent = _create(client, headers, {"name": "父目录", "scope": "general"})
    _create(client, headers, {"name": "子目录", "scope": "general", "parent_id": parent["id"]})

    refused = client.delete(f"/api/v1/folders/{parent['id']}", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "folder_not_empty"

    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert [n["name"] for n in tree] == ["父目录"]


def test_delete_leaf_folder(client, headers) -> None:
    leaf = _create(client, headers, {"name": "可删", "scope": "general"})
    response = client.delete(f"/api/v1/folders/{leaf['id']}", headers=headers)
    assert response.status_code == 204
    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert tree == []


def test_folder_in_missing_project_rejected(client, headers) -> None:
    response = client.post("/api/v1/folders", json={"name": "孤儿", "scope": "project", "project_id": 999}, headers=headers)
    assert response.status_code == 404


def test_folder_stats_and_cascade_delete(iso_client, headers, tmp_path) -> None:
    import time

    def wait_import(job_id: int):
        for _ in range(300):
            res = iso_client.get(f"/api/v1/imports/{job_id}", headers=headers).json()
            if res["status"] in {"completed", "failed"}:
                assert res["status"] == "completed"
                return res
            time.sleep(0.02)
        raise AssertionError("import timeout")

    # Create Parent -> Child folder structure
    parent = _create(iso_client, headers, {"name": "父级", "scope": "general"})
    child = _create(iso_client, headers, {"name": "子级", "scope": "general", "parent_id": parent["id"]})

    # Add file to parent
    f1 = tmp_path / "f1.txt"
    f1.write_text("file 1", encoding="utf-8")
    j1 = iso_client.post("/api/v1/imports", json={"paths": [str(f1)], "folder_id": parent["id"]}, headers=headers).json()
    wait_import(j1["id"])

    # Add file to child
    f2 = tmp_path / "f2.txt"
    f2.write_text("file 2", encoding="utf-8")
    j2 = iso_client.post("/api/v1/imports", json={"paths": [str(f2)], "folder_id": child["id"]}, headers=headers).json()
    wait_import(j2["id"])

    # Test folder stats
    stats = iso_client.get(f"/api/v1/folders/{parent['id']}/stats", headers=headers)
    assert stats.status_code == 200
    data = stats.json()
    assert data["folder_id"] == parent["id"]
    assert data["folder_name"] == "父级"
    assert data["subfolder_count"] == 1
    assert data["asset_count"] == 2
    assert data["managed_asset_count"] == 2
    assert data["external_asset_count"] == 0

    # Default delete without cascade should fail with 409
    refused = iso_client.delete(f"/api/v1/folders/{parent['id']}", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "folder_not_empty"

    # Cascade delete should succeed with 204
    cascade = iso_client.delete(f"/api/v1/folders/{parent['id']}?cascade=true", headers=headers)
    assert cascade.status_code == 204

    # Tree should now be empty
    tree = iso_client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert tree == []

    # Assets should now be in trash
    trash = iso_client.get("/api/v1/trash", headers=headers).json()
    assert trash["total"] == 2
    trashed_ids = [item["id"] for item in trash["items"]]

    # Restore one asset: original folder was deleted, should fallback to auto-created or general folder
    restored = iso_client.post(f"/api/v1/trash/{trashed_ids[0]}/restore", headers=headers)
    assert restored.status_code == 204

    # The restored asset is now active in general
    assets = iso_client.get("/api/v1/assets", params={"scope": "general"}, headers=headers).json()
    assert assets["total"] == 1
    assert assets["items"][0]["id"] == trashed_ids[0]


def test_folder_lock_blocks_direct_delete(client, headers) -> None:
    folder = _create(client, headers, {"name": "锁定目录", "scope": "general"})

    locked = client.patch(f"/api/v1/folders/{folder['id']}", json={"locked": True}, headers=headers)
    assert locked.status_code == 200
    assert locked.json()["locked"] is True

    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert tree[0]["locked"] is True

    refused = client.delete(f"/api/v1/folders/{folder['id']}", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "folder_locked"

    refused_cascade = client.delete(f"/api/v1/folders/{folder['id']}?cascade=true", headers=headers)
    assert refused_cascade.status_code == 409

    unlocked = client.patch(f"/api/v1/folders/{folder['id']}", json={"locked": False}, headers=headers)
    assert unlocked.json()["locked"] is False
    assert client.delete(f"/api/v1/folders/{folder['id']}", headers=headers).status_code == 204


def test_lock_does_not_inherit_and_allows_rename_move(client, headers) -> None:
    parent = _create(client, headers, {"name": "锁定父", "scope": "general"})
    child = _create(client, headers, {"name": "子目录", "scope": "general", "parent_id": parent["id"]})
    new_home = _create(client, headers, {"name": "新归属", "scope": "general"})
    client.patch(f"/api/v1/folders/{parent['id']}", json={"locked": True}, headers=headers)

    # 锁定不向下继承：子目录可单独删除
    assert client.delete(f"/api/v1/folders/{child['id']}", headers=headers).status_code == 204

    # 锁定目录本身仍可重命名与移动（锁只拦删除）
    renamed = client.patch(f"/api/v1/folders/{parent['id']}", json={"name": "锁定父改名"}, headers=headers)
    assert renamed.status_code == 200
    moved = client.patch(f"/api/v1/folders/{parent['id']}", json={"parent_id": new_home["id"]}, headers=headers)
    assert moved.status_code == 200

    # 删除仍被拦截
    assert client.delete(f"/api/v1/folders/{parent['id']}?cascade=true", headers=headers).status_code == 409


def test_cascade_delete_blocked_by_locked_descendant(client, headers) -> None:
    top = _create(client, headers, {"name": "顶层", "scope": "general"})
    mid = _create(client, headers, {"name": "中层", "scope": "general", "parent_id": top["id"]})
    leaf = _create(client, headers, {"name": "锁定叶子", "scope": "general", "parent_id": mid["id"]})
    client.patch(f"/api/v1/folders/{leaf['id']}", json={"locked": True}, headers=headers)

    refused = client.delete(f"/api/v1/folders/{top['id']}?cascade=true", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "folder_locked"
    assert "锁定叶子" in refused.json()["error"]["message"]

    # 整次拦截：范围内目录全部完好
    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert [n["name"] for n in tree] == ["顶层"]
    assert client.get(f"/api/v1/folders/{leaf['id']}/stats", headers=headers).status_code == 200

    # 解锁后级联成功
    client.patch(f"/api/v1/folders/{leaf['id']}", json={"locked": False}, headers=headers)
    assert client.delete(f"/api/v1/folders/{top['id']}?cascade=true", headers=headers).status_code == 204


def test_project_cascade_delete_blocked_by_locked_folder(client, headers) -> None:
    project = client.post("/api/v1/projects", json={"name": "级联项目"}, headers=headers).json()
    folder = _create(client, headers, {"name": "锁定项目目录", "scope": "project", "project_id": project["id"]})
    client.patch(f"/api/v1/folders/{folder['id']}", json={"locked": True}, headers=headers)

    refused = client.delete(f"/api/v1/projects/{project['id']}?cascade=true", headers=headers)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "folder_locked"

    client.patch(f"/api/v1/folders/{folder['id']}", json={"locked": False}, headers=headers)
    assert client.delete(f"/api/v1/projects/{project['id']}?cascade=true", headers=headers).status_code == 204


def test_folder_description_persist_strip_and_clear(client, headers) -> None:
    folder = _create(client, headers, {"name": "备注目录", "scope": "general"})

    saved = client.patch(f"/api/v1/folders/{folder['id']}", json={"description": "  收集说明  "}, headers=headers)
    assert saved.status_code == 200
    assert saved.json()["description"] == "收集说明"

    # 编辑锁定时未提供 description 键 → 保持不变
    locked = client.patch(f"/api/v1/folders/{folder['id']}", json={"locked": True}, headers=headers)
    assert locked.json()["description"] == "收集说明"

    # 全空白清空
    blank = client.patch(f"/api/v1/folders/{folder['id']}", json={"description": "   "}, headers=headers)
    assert blank.json()["description"] is None

    # 显式 null 清空
    client.patch(f"/api/v1/folders/{folder['id']}", json={"description": "再写点"}, headers=headers)
    cleared = client.patch(f"/api/v1/folders/{folder['id']}", json={"description": None}, headers=headers)
    assert cleared.json()["description"] is None

    too_long = client.patch(f"/api/v1/folders/{folder['id']}", json={"description": "x" * 2001}, headers=headers)
    assert too_long.status_code == 422


def test_pinned_folder_sorts_first_at_its_level(client, headers) -> None:
    _create(client, headers, {"name": "韩系跳舞穿搭", "scope": "general"})
    _create(client, headers, {"name": "法Q啊", "scope": "general"})
    drafts = _create(client, headers, {"name": "未整理草稿", "scope": "general"})

    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert [n["name"] for n in tree] == ["韩系跳舞穿搭", "法Q啊", "未整理草稿"]
    assert all(not n["pinned"] for n in tree)

    pinned = client.patch(f"/api/v1/folders/{drafts['id']}", json={"pinned": True}, headers=headers)
    assert pinned.status_code == 200
    assert pinned.json()["pinned"] is True

    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert [n["name"] for n in tree] == ["未整理草稿", "韩系跳舞穿搭", "法Q啊"]

    # 置顶只作用于所在层：其子目录不受影响，同级内部保持原 sort_order 相对序
    _create(client, headers, {"name": "子目录A", "scope": "general", "parent_id": drafts["id"]})
    child_b = _create(client, headers, {"name": "子目录B", "scope": "general", "parent_id": drafts["id"]})
    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert [n["name"] for n in tree[0]["children"]] == ["子目录A", "子目录B"]
    # 置顶只作用于所在层：B 在其所在层排最前，根层顺序不变
    client.patch(f"/api/v1/folders/{child_b['id']}", json={"pinned": True}, headers=headers)
    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert [n["name"] for n in tree] == ["未整理草稿", "韩系跳舞穿搭", "法Q啊"]
    assert [n["name"] for n in tree[0]["children"]] == ["子目录B", "子目录A"]

    unpinned = client.patch(f"/api/v1/folders/{drafts['id']}", json={"pinned": False}, headers=headers)
    assert unpinned.json()["pinned"] is False
    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert [n["name"] for n in tree] == ["韩系跳舞穿搭", "法Q啊", "未整理草稿"]


def test_pinned_defaults_false_and_survives_other_patches(client, headers) -> None:
    folder = _create(client, headers, {"name": "默认未置顶", "scope": "general"})
    assert folder["pinned"] is False
    # 未提供 pinned 的 PATCH（改名/锁定）不得悄悄重置置顶状态
    client.patch(f"/api/v1/folders/{folder['id']}", json={"pinned": True}, headers=headers)
    renamed = client.patch(
        f"/api/v1/folders/{folder['id']}", json={"name": "改名不丢置顶", "locked": True}, headers=headers
    )
    assert renamed.json()["pinned"] is True
    assert renamed.json()["locked"] is True
    tree = client.get("/api/v1/folders/tree", params={"scope": "general"}, headers=headers).json()
    assert tree[0]["pinned"] is True
    assert tree[0]["name"] == "改名不丢置顶"


def test_folder_edit_dialog_combined_patch(client, headers) -> None:
    folder = _create(client, headers, {"name": "编辑我", "scope": "general"})
    edited = client.patch(
        f"/api/v1/folders/{folder['id']}",
        json={"name": "已改名", "locked": True, "description": "改名+锁定+备注一起保存"},
        headers=headers,
    )
    assert edited.status_code == 200
    body = edited.json()
    assert body["name"] == "已改名"
    assert body["locked"] is True
    assert body["description"] == "改名+锁定+备注一起保存"

