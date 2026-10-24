from __future__ import annotations

import os
import platform
import string

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.models.asset import Asset
from backend.app.models.folder import Folder


def make_app(db_path) -> TestClient:
    return TestClient(create_app("test-token", db_path=str(db_path)))


def test_default_managed_root_seeded(client, headers) -> None:
    settings = client.get("/api/v1/settings", headers=headers).json()
    assert settings["managed_root"] == "D:\\Ryan_DAM\\assets"
    assert settings["managed_root_state"] in {"ok", "missing", "unavailable"}


def test_update_managed_root_round_trip(client, headers, tmp_path) -> None:
    target = tmp_path / "assets"
    target.mkdir()
    updated = client.patch("/api/v1/settings", json={"managed_root": str(target)}, headers=headers)
    assert updated.status_code == 200
    body = updated.json()
    assert body["managed_root"] == str(target)
    assert body["managed_root_state"] == "ok"

    fetched = client.get("/api/v1/settings", headers=headers).json()
    assert fetched["managed_root"] == str(target)


def test_relative_path_rejected(client, headers) -> None:
    response = client.patch("/api/v1/settings", json={"managed_root": "relative/path"}, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"

    empty = client.patch("/api/v1/settings", json={"managed_root": "   "}, headers=headers)
    assert empty.status_code == 422


def test_unavailable_drive_reported(client, headers) -> None:
    if platform.system() != "Windows":
        return  # drive-letter logic is Windows-only
    free_letters = [L for L in string.ascii_uppercase if not os.path.exists(L + os.sep)]
    if not free_letters:
        return  # no removable candidate letter on this machine
    drive = free_letters[-1]
    response = client.patch("/api/v1/settings", json={"managed_root": f"{drive}:\\Ryan_DAM\\assets"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["managed_root_state"] == "unavailable"


def test_changing_root_does_not_touch_existing_asset_paths(tmp_path, headers) -> None:
    db_path = tmp_path / "settings.sqlite3"
    old_root = tmp_path / "old-assets"
    old_root.mkdir()
    with make_app(db_path) as first:
        folder = first.post("/api/v1/folders", json={"name": "图", "scope": "general"}, headers=headers).json()
        session_factory = first.app.state.session_factory
        with session_factory() as session:
            session.add(
                Asset(
                    folder_id=folder["id"],
                    name="hero.png",
                    asset_type="image",
                    size_bytes=123,
                    file_path=str(old_root / "hero.png"),
                    source_type="managed",
                )
            )
            session.commit()

        first.patch("/api/v1/settings", json={"managed_root": str(tmp_path / "new-assets")}, headers=headers)

    with make_app(db_path) as second:
        session_factory = second.app.state.session_factory
        with session_factory() as session:
            asset = session.query(Asset).one()
            assert asset.file_path == str(old_root / "hero.png")
            assert asset.folder_id == folder_id_of(session, "图")
            assert asset.source_type == "managed"
        settings = second.get("/api/v1/settings", headers=headers).json()
        assert settings["managed_root"] == str(tmp_path / "new-assets")


def folder_id_of(session, name: str) -> int:
    return session.query(Folder).filter(Folder.name == name).one().id
