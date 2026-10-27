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
    "ai_provider_instances",
    "ai_model_profiles",
    "ai_default_bindings",
    "ai_reverse_templates",
    "ai_creation_presets",
    "ai_tasks",
    "ai_task_items",
    "ai_task_references",
    "ai_results",
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
    provider_columns = {c["name"] for c in inspector.get_columns("ai_provider_instances")}
    assert {"family", "name", "base_url", "credential_ref", "enabled"} <= provider_columns
    model_columns = {c["name"] for c in inspector.get_columns("ai_model_profiles")}
    assert {"provider_id", "model_id", "name", "adapter_kind", "capabilities_json"} <= model_columns
    binding_columns = {c["name"] for c in inspector.get_columns("ai_default_bindings")}
    assert {"capability", "scene", "model_profile_id"} <= binding_columns
    asset_columns = {c["name"] for c in inspector.get_columns("assets")}
    assert {"asset_origin", "prompt_origin", "prompt_revision", "generation_task_id", "generation_result_id"} <= asset_columns

    version = engine.connect().exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
    assert version == "0014"


def test_migrations_are_idempotent(tmp_path) -> None:
    db_path = tmp_path / "repeat.sqlite3"
    run_migrations(db_path)
    run_migrations(db_path)


def test_data_persists_across_restart(tmp_path) -> None:
    db_path = tmp_path / "persist.sqlite3"
    run_migrations(db_path)
    engine = create_sqlite_engine(db_path)
