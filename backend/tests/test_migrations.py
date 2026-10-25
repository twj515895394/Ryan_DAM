from __future__ import annotations

from sqlalchemy import inspect

from backend.app.db.migrations import run_migrations
from backend.app.db.session import create_session_factory, create_sqlite_engine
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
    version = engine.connect().exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
    assert version == "0005"


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
