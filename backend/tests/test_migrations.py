from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import inspect

from backend.app.db.migrations import run_migrations
from backend.app.db.session import create_session_factory, create_sqlite_engine
from backend.app.models.asset import Asset
from backend.app.models.project import Project

EXPECTED_TABLES = {
    "projects",
    "folders",
    "assets",
    "external_sources",
    "tags",
    "asset_tags",
    "import_jobs",
    "import_job_items",
    "app_settings",
    "alembic_version",
}


def test_fresh_database_migrates_all_tables(tmp_path) -> None:
    db_path = tmp_path / "fresh.sqlite3"
    run_migrations(db_path)
    engine = create_sqlite_engine(db_path)
    inspector = inspect(engine)
    assert EXPECTED_TABLES.issubset(set(inspector.get_table_names()))
    folder_columns = {c["name"] for c in inspector.get_columns("folders")}
    assert {"pinned", "locked", "description"} <= folder_columns
    source_columns = {c["name"] for c in inspector.get_columns("external_sources")}
    assert "mount_folder" in source_columns
    version = engine.connect().exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
    assert version == "0009"


def test_migrations_are_idempotent(tmp_path) -> None:
    db_path = tmp_path / "repeat.sqlite3"
    run_migrations(db_path)
    run_migrations(db_path)


def test_data_persists_across_restart(tmp_path) -> None:
    db_path = tmp_path / "persist.sqlite3"
    run_migrations(db_path)
    engine = create_sqlite_engine(db_path)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(Project(name="Persisted"))
        session.commit()

    reopened = create_sqlite_engine(db_path)
    with create_session_factory(reopened)() as session:
        names = [p.name for p in session.query(Project).all()]
    assert names == ["Persisted"]


def _load_migration_0008():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0008_asset_code_to_other.py"
    spec = importlib.util.spec_from_file_location("m0008_asset_code_to_other", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_0008_reclassifies_code_documents(tmp_path) -> None:
    db_path = tmp_path / "code.sqlite3"
    run_migrations(db_path)
    engine = create_sqlite_engine(db_path)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(Asset(name="build.py", file_path="objects/a", source_type="managed", asset_type="document"))
        session.add(Asset(name="config.yaml", file_path="objects/b", source_type="managed", asset_type="document"))
        session.add(Asset(name="report.pdf", file_path="objects/c", source_type="managed", asset_type="document"))
        session.add(Asset(name="archive.zip", file_path="objects/d", source_type="managed", asset_type="other"))
        session.commit()

    m = _load_migration_0008()
    with engine.connect() as conn:
        assert m.reclassify_code_documents(conn) == 2
        conn.commit()
        assert m.reclassify_code_documents(conn) == 0  # 幂等

    with session_factory() as session:
        types = {a.name: a.asset_type for a in session.query(Asset).all()}
    assert types == {
        "build.py": "other",
        "config.yaml": "other",
        "report.pdf": "document",
        "archive.zip": "other",
    }
