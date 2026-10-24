"""Managed import pipeline: space precheck → staging copy + hash → atomic move → asset row.

Runs on a single dedicated worker thread (V1); SQLite writes stay serialized.
Files land at `<managed_root>/objects/<asset-id>/<filename>`; staging lives at
`<managed_root>/.staging/<job-id>/`. The managed root only affects NEW imports.
"""

from __future__ import annotations

import mimetypes
import os
import queue
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.errors import ApiError
from backend.app.models.asset import Asset
from backend.app.models.folder import Folder
from backend.app.models.import_job import ImportJob, ImportJobItem
from backend.app.services.folder_service import ensure_folder_path
from backend.app.services.settings_service import get_managed_root

disk_usage = shutil.disk_usage

SPACE_MARGIN_FACTOR = 1.1
CHUNK_SIZE = 1024 * 1024

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".avif", ".ico", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv", ".wmv"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
DOC_EXTS = {".pdf", ".txt", ".md", ".json", ".csv", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}

JOB_TERMINAL = {"completed", "completed_with_errors", "failed", "interrupted"}


def guess_asset_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in DOC_EXTS:
        return "document"
    return "other"


def _managed_layout(managed_root: str) -> tuple[Path, Path]:
    root = Path(managed_root)
    try:
        (root / "objects").mkdir(parents=True, exist_ok=True)
        staging = root / ".staging"
        staging.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ApiError("storage_unavailable", f"托管存储位置不可用：{error}", 400) from error
    return root / "objects", staging


def _precheck_space(paths: list[Path], managed_root: str) -> None:
    drive, _ = os.path.splitdrive(managed_root)
    probe = drive + os.sep if drive else managed_root
    try:
        usage = disk_usage(probe)
    except OSError as error:
        raise ApiError("storage_unavailable", f"目标磁盘不可用：{error}", 400) from error
    required = int(sum(p.stat().st_size for p in paths if p.exists()) * SPACE_MARGIN_FACTOR)
    if usage.free < required:
        free_gb = usage.free / 1024**3
        need_gb = required / 1024**3
        raise ApiError(
            "insufficient_space",
            f"目标磁盘空间不足：预计需要 {need_gb:.2f} GB，当前可用 {free_gb:.2f} GB。请更换存储位置或取消导入。",
            400,
        )


class ImportWorker:
    """Single background worker processing one queued job at a time."""

    def __init__(self) -> None:
        self._queue: queue.Queue[int] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def ensure_started(self, session_factory: sessionmaker) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run, args=(session_factory,), daemon=True, name="ryan-dam-import-worker"
            )
            self._thread.start()

    def submit(self, job_id: int) -> None:
        self._queue.put(job_id)

    def _run(self, session_factory: sessionmaker) -> None:
        while True:
            job_id = self._queue.get()
            try:
                _process_job(session_factory, job_id)
            except Exception as error:  # noqa: BLE001 - worker must never die
                _mark_job_failed_hard(session_factory, job_id, str(error))
            finally:
                self._queue.task_done()


def recover_stale_jobs(session_factory: sessionmaker) -> None:
    """Mark jobs left running by a previous process as interrupted."""
    with session_factory() as session:
        stale = session.scalars(select(ImportJob).where(ImportJob.status.in_(["queued", "running"]))).all()
        for job in stale:
            job.status = "interrupted"
            job.message = "应用关闭导致导入中断，可重试失败项。"
            for item in session.scalars(
                select(ImportJobItem).where(
                    ImportJobItem.job_id == job.id, ImportJobItem.status.in_(["pending", "processing"])
                )
            ):
                item.status = "failed"
                item.error_message = "应用关闭导致导入中断。"
        if stale:
            session.commit()


def create_import(
    db: Session,
    *,
    paths: list[str],
    folder_id: int,
    allow_duplicates: bool = False,
) -> ImportJob:
    if not paths:
        raise ApiError("validation_error", "导入列表不能为空。", 422)
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise ApiError("not_found", "目标目录不存在或已被删除。", 404)

    unique_paths = list(dict.fromkeys(paths))
    sources: list[Path] = []
    for raw in unique_paths:
        path = Path(raw)
        if not path.is_absolute():
            raise ApiError("validation_error", f"导入路径必须是绝对路径：{raw}", 422)
        sources.append(path)

    managed_root = get_managed_root(db)
    _precheck_space([p for p in sources if p.exists()], managed_root)

    job = ImportJob(
        job_type="managed_files",
        status="queued",
        target_folder_id=folder_id,
        allow_duplicates=allow_duplicates,
        total_count=len(sources),
    )
    db.add(job)
    db.flush()
    for path in sources:
        db.add(ImportJobItem(job_id=job.id, source_path=str(path), status="pending"))
    db.commit()
    db.refresh(job)

    factory = _factory_holder.get("factory")
    job_worker = _factory_holder.get("worker")
    if not isinstance(factory, sessionmaker) or not isinstance(job_worker, ImportWorker):
        raise ApiError("db_unavailable", "导入服务尚未初始化。", 500)
    job_worker.ensure_started(factory)
    job_worker.submit(job.id)
    return job


def create_folder_import(
    db: Session,
    *,
    source_dir: str,
    folder_id: int,
    allow_duplicates: bool = False,
) -> ImportJob:
    """Import a whole directory, mirroring its sub-hierarchy into logical folders."""
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise ApiError("not_found", "目标目录不存在或已被删除。", 404)
    root = Path(source_dir)
    if not root.is_dir():
        raise ApiError("invalid_source", f"源文件夹不存在或不可访问：{source_dir}", 400)

    files = sorted(p for p in root.rglob("*") if p.is_file())
    if not files:
        raise ApiError("invalid_source", "源文件夹内没有可导入的文件。", 400)

    managed_root = get_managed_root(db)
    _precheck_space(files, managed_root)

    job = ImportJob(
        job_type="managed_folder",
        status="queued",
        target_folder_id=folder_id,
        allow_duplicates=allow_duplicates,
        total_count=len(files),
    )
    db.add(job)
    db.flush()
    for path in files:
        relative = path.relative_to(root)
        target = ensure_folder_path(db, base=folder, parts=list(relative.parts[:-1]))
        db.add(
            ImportJobItem(
                job_id=job.id,
                source_path=str(path),
                status="pending",
                target_folder_id=target.id,
            )
        )
    db.commit()
    db.refresh(job)

    factory = _factory_holder.get("factory")
    job_worker = _factory_holder.get("worker")
    if not isinstance(factory, sessionmaker) or not isinstance(job_worker, ImportWorker):
        raise ApiError("db_unavailable", "导入服务尚未初始化。", 500)
    job_worker.ensure_started(factory)
    job_worker.submit(job.id)
    return job


_factory_holder: dict[str, object] = {}


def bind_worker_factory(session_factory: sessionmaker) -> None:
    """Wire one worker per application instance; tests create many apps."""
    _factory_holder["factory"] = session_factory
    _factory_holder["worker"] = ImportWorker()
    recover_stale_jobs(session_factory)


def retry_failed(job_id: int) -> None:
    """Requeue only failed/interrupted items; successful items are never reprocessed."""
    factory = _factory_holder.get("factory")
    job_worker = _factory_holder.get("worker")
    if not isinstance(factory, sessionmaker) or not isinstance(job_worker, ImportWorker):
        raise ApiError("db_unavailable", "导入服务尚未初始化。", 500)
    with factory() as session:
        job = session.get(ImportJob, job_id)
        if job is None:
            raise ApiError("not_found", "导入任务不存在。", 404)
        if job.status in {"queued", "running"}:
            raise ApiError("job_in_progress", "导入任务仍在进行中，不能重试。", 409)
        failed_items = session.scalars(
            select(ImportJobItem).where(ImportJobItem.job_id == job_id, ImportJobItem.status == "failed")
        ).all()
        if not failed_items:
            raise ApiError("nothing_to_retry", "没有可重试的失败项。", 409)
        for item in failed_items:
            item.status = "pending"
            item.error_message = None
            item.retry_count = (item.retry_count or 0) + 1
        job.status = "queued"
        job.message = None
        job.stage = None
        job.finished_at = None
        session.commit()

    job_worker.ensure_started(factory)
    job_worker.submit(job_id)


def _mark_job_failed_hard(session_factory: sessionmaker, job_id: int, message: str) -> None:
    with session_factory() as session:
        job = session.get(ImportJob, job_id)
        if job is None:
            return
        job.status = "failed"
        job.message = message
        for item in session.scalars(
            select(ImportJobItem).where(ImportJobItem.job_id == job_id, ImportJobItem.status != "success")
        ):
            item.status = "failed"
            item.error_message = message
        session.commit()


def _process_job(session_factory: sessionmaker, job_id: int) -> None:
    with session_factory() as session:
        job = session.get(ImportJob, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "running"
        job.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()
        items = session.scalars(
            select(ImportJobItem).where(ImportJobItem.job_id == job_id).order_by(ImportJobItem.id)
        ).all()

    for item in items:
        _process_item(session_factory, job_id, item.id)

    with session_factory() as session:
        job = session.get(ImportJob, job_id)
        if job is None:
            return
        counts = {"success": 0, "skipped": 0, "failed": 0}
        for item in session.scalars(select(ImportJobItem).where(ImportJobItem.job_id == job_id)):
            counts[item.status] = counts.get(item.status, 0) + 1
        job.success_count = counts["success"]
        job.skipped_count = counts["skipped"]
        job.failed_count = counts["failed"]
        if job.status == "running":
            if counts["failed"] and (counts["success"] or counts["skipped"]):
                job.status = "completed_with_errors"
            elif counts["failed"]:
                job.status = "failed"
                job.message = "全部文件导入失败，请查看失败原因。"
            else:
                job.status = "completed"
        job.stage = "done"
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()
        _cleanup_staging(session, job)


def _cleanup_staging(session: Session, job: ImportJob) -> None:
    try:
        root = Path(get_managed_root(session))
        staging_job = root / ".staging" / str(job.id)
        if staging_job.exists():
            shutil.rmtree(staging_job, ignore_errors=True)
    except Exception:  # noqa: BLE001 - cleanup is best-effort
        pass


def _process_item(session_factory: sessionmaker, job_id: int, item_id: int) -> None:
    with session_factory() as session:
        job = session.get(ImportJob, job_id)
        item = session.get(ImportJobItem, item_id)
        if job is None or item is None or item.status != "pending":
            return
        item.status = "processing"
        session.commit()
        target_folder_id = item.target_folder_id or job.target_folder_id
        allow_duplicates = job.allow_duplicates

    source = Path(item.source_path)
    if not source.is_file():
        _fail_item(session_factory, item_id, f"源文件不存在或不可读：{source}")
        return

    with session_factory() as session:
        managed_root = get_managed_root(session)
    try:
        objects_dir, staging_dir = _managed_layout(managed_root)
    except ApiError as error:
        _fail_item(session_factory, item_id, error.message)
        return

    job_staging = staging_dir / str(job_id)
    try:
        job_staging.mkdir(parents=True, exist_ok=True)
        staged = job_staging / f"{item_id}_{source.name}"
        sha256 = _copy_with_hash(source, staged)
        if staged.stat().st_size != source.stat().st_size:
            raise OSError("复制后大小校验失败")

        with session_factory() as session:
            duplicate = session.scalar(
                select(Asset).where(Asset.sha256 == sha256, Asset.status == "active")
            )
            if duplicate is not None and not allow_duplicates:
                item = session.get(ImportJobItem, item_id)
                item.status = "skipped"
                item.error_message = "内容重复已跳过（可在导入时选择强制导入）。"
                session.commit()
                staged.unlink(missing_ok=True)
                return

            asset = Asset(
                folder_id=target_folder_id,
                name=source.name,
                extension=source.suffix.lstrip(".") or None,
                mime_type=mimetypes.guess_type(source.name)[0],
                asset_type=guess_asset_type(source),
                size_bytes=source.stat().st_size,
                file_path=str(staged),
                source_type="managed",
                sha256=sha256,
            )
            session.add(asset)
            session.flush()
            final_dir = objects_dir / str(asset.id)
            final_dir.mkdir(parents=True, exist_ok=True)
            final_path = final_dir / source.name
            os.replace(staged, final_path)
            asset.file_path = str(final_path)
            item = session.get(ImportJobItem, item_id)
            item.status = "success"
            item.asset_id = asset.id
            session.commit()
    except Exception as error:  # noqa: BLE001 - any failure must not leave half files
        staged_cleanup = job_staging / f"{item_id}_{source.name}"
        try:
            staged_cleanup.unlink(missing_ok=True)
        except OSError:
            pass
        _fail_item(session_factory, item_id, f"导入失败：{error}")


def _copy_with_hash(source: Path, destination: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(source, "rb") as src, open(destination, "wb") as dst:
        while True:
            chunk = src.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            dst.write(chunk)
    return digest.hexdigest()


def _fail_item(session_factory: sessionmaker, item_id: int, message: str) -> None:
    with session_factory() as session:
        item = session.get(ImportJobItem, item_id)
        if item is None or item.status == "success":
            return
        item.status = "failed"
        item.error_message = message
        session.commit()
