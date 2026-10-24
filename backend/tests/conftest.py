from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app("test-token", db_path=str(tmp_path / "ryan_dam.sqlite3"))


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def headers():
    return {"Host": "127.0.0.1", "X-Ryan-DAM-Token": "test-token"}


def make_app(db_path) -> TestClient:
    return TestClient(create_app("test-token", db_path=str(db_path)))
