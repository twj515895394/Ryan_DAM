"""Programmatic Alembic runner used at backend startup."""

from __future__ import annotations

import sys
from pathlib import Path


def alembic_script_location() -> Path:
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", ".")) / "alembic"
        if bundled.exists():
            return bundled
    return Path(__file__).resolve().parents[2] / "alembic"


def run_migrations(db_path: Path | str) -> None:
    from alembic import command
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", str(alembic_script_location()))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(db_path)}")
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
