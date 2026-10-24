from __future__ import annotations

import hmac
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.v1 import api_router
from backend.app.core.errors import ApiError, api_error_handler
from backend.app.db.migrations import run_migrations
from backend.app.db.session import create_session_factory, create_sqlite_engine
from backend.app.services.import_service import bind_worker_factory
from backend.app.services.settings_service import seed_default_settings

APP_VERSION = "0.1.0"
READY_PREFIX = "RYAN_DAM_READY "
ALLOWED_ORIGINS = {"null", "http://127.0.0.1:5173", "http://localhost:5173"}
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


def default_db_path(data_dir: Path | None = None) -> Path:
    configured = os.environ.get("RYAN_DAM_DB_PATH")
    if configured:
        return Path(configured)
    base = data_dir or Path(os.environ.get("RYAN_DAM_DATA_DIR", str(Path.home() / ".ryan_dam" / "data")))
    return base / "ryan_dam.sqlite3"


def init_database(db_path: Path | str) -> tuple[Any, Any]:
    """Run Alembic migrations, then return (engine, session_factory)."""
    run_migrations(db_path)
    engine = create_sqlite_engine(db_path)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_default_settings(session)
    return engine, session_factory


def create_app(api_token: str | None = None, db_path: str | None = None) -> FastAPI:
    expected_token = api_token if api_token is not None else os.environ.get("RYAN_DAM_API_TOKEN", "")
    application = FastAPI(
        title="Ryan_DAM Local API",
        version=APP_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.api_token = expected_token
    application.state.server = None
    application.state.session_factory = None
    if db_path:
        _engine, application.state.session_factory = init_database(db_path)
        bind_worker_factory(application.state.session_factory)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(ALLOWED_ORIGINS),
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Ryan-DAM-Token"],
        allow_credentials=False,
        max_age=300,
    )
    application.add_exception_handler(ApiError, api_error_handler)
    application.include_router(api_router)

    @application.middleware("http")
    async def local_api_guard(request: Request, call_next: Any):
        if request.url.hostname not in ALLOWED_HOSTS:
            return JSONResponse(status_code=403, content={"detail": "Only loopback Host values are accepted."})
        origin = request.headers.get("origin")
        if origin is not None and origin not in ALLOWED_ORIGINS:
            return JSONResponse(status_code=403, content={"detail": "Origin is not allowed."})
        if request.method == "OPTIONS":
            return await call_next(request)
        token = request.headers.get("x-ryan-dam-token", "")
        expected = request.app.state.api_token or ""
        if not expected or not hmac.compare_digest(token, expected):
            return JSONResponse(status_code=401, content={"detail": "A valid local API token is required."})
        return await call_next(request)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": APP_VERSION}

    @application.post("/shutdown", status_code=202)
    async def shutdown() -> dict[str, str]:
        server = application.state.server
        if server is not None:
            server.should_exit = True
        return {"status": "shutting_down"}

    return application


def run_server() -> None:
    token = os.environ.get("RYAN_DAM_API_TOKEN", "")
    if not token:
        print("RYAN_DAM_API_TOKEN is required; launch this process through Electron.", file=sys.stderr)
        raise SystemExit(2)
    data_dir = Path(os.environ.get("RYAN_DAM_DATA_DIR", str(Path.home() / ".ryan_dam" / "data")))
    data_dir.mkdir(parents=True, exist_ok=True)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    listener.setblocking(False)
    port = listener.getsockname()[1]

    application = create_app(token, db_path=str(default_db_path(data_dir)))
    config = uvicorn.Config(application, host="127.0.0.1", port=port, log_level=os.environ.get("RYAN_DAM_LOG_LEVEL", "info").lower(), access_log=False)
    server = uvicorn.Server(config)
    application.state.server = server
    print(READY_PREFIX + json.dumps({"host": "127.0.0.1", "port": port, "version": APP_VERSION}, separators=(",", ":")), flush=True)
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()


app = create_app()

if __name__ == "__main__":
    run_server()
