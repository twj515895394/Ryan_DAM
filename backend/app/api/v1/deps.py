from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.core.errors import ApiError


def get_db(request: Request) -> Iterator[Session]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise ApiError("db_unavailable", "本地数据库尚未初始化。", 500)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
