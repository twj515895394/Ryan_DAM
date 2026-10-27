from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Coroutine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.errors import ApiError
from backend.app.db.base import utcnow
from backend.app.models.ai.task import AiTask, AiTaskItem, AiTaskReference, AiResult

logger = logging.getLogger(__name__)

# 状态机合法流转映射
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "canceled"},
    "running": {"succeeded", "partial_failed", "failed", "cancel_requested", "recovery_needed"},
    "cancel_requested": {"canceled", "succeeded", "failed"},
    "recovery_needed": {"running", "failed"},
    "failed": {"queued"},  # retry 会创建带 retry_of 的新任务，但若原任务直接排队也允许
    "succeeded": set(),
    "partial_failed": set(),
    "canceled": set(),
}


class AiTaskScheduler:
    """进程内有界并发 AI 异步任务调度器。"""

    def __init__(
        self,
        session_factory: sessionmaker,
        max_global_concurrency: int = 3,
        per_provider_concurrency: int = 2,
    ) -> None:
        self.session_factory = session_factory
        self.max_global_concurrency = max_global_concurrency
        self.per_provider_concurrency = per_provider_concurrency

        self._semaphore = asyncio.Semaphore(max_global_concurrency)
        self._provider_semaphores: dict[int, asyncio.Semaphore] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """注册调度器绑定的全局事件循环。"""
        self._loop = loop

    def _get_provider_semaphore(self, provider_id: int | None) -> asyncio.Semaphore:
        pid = provider_id or 0
        if pid not in self._provider_semaphores:
            self._provider_semaphores[pid] = asyncio.Semaphore(self.per_provider_concurrency)
        return self._provider_semaphores[pid]

    def create_task(
        self,
        db: Session,
        task_type: str,
        provider_id: int | None = None,
        model_profile_id: int | None = None,
        preset_id: int | None = None,
        prompt_final: str | None = None,
        raw_user_request: str | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        retry_of: str | None = None,
    ) -> AiTask:
        """在数据库中创建任务记录，状态为 queued。"""
        task_id = f"aitask_{uuid.uuid4().hex[:16]}"
        task = AiTask(
            id=task_id,
            task_type=task_type,
            provider_id=provider_id,
            model_profile_id=model_profile_id,
            preset_id=preset_id,
            status="queued",
            prompt_final=prompt_final,
            raw_user_request=raw_user_request,
            params_json="{}",
            idempotency_key=idempotency_key,
            retry_of=retry_of,
        )
        if params:
            task.params = params
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def update_task_status(
        self,
        task_id: str,
        target_status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        progress_pct: int | None = None,
    ) -> None:
        """受控状态机流转。"""
        with self.session_factory() as db:
            task = db.query(AiTask).filter(AiTask.id == task_id).first()
            if not task:
                return

            current_status = task.status
            allowed = ALLOWED_TRANSITIONS.get(current_status, set())
            if target_status not in allowed and target_status != current_status:
                logger.warning(
                    f"Invalid status transition for task {task_id}: {current_status} -> {target_status}"
                )
                return

            task.status = target_status
            if error_code is not None:
                task.error_code = error_code
            if error_message is not None:
                task.error_message = error_message
            if progress_pct is not None:
                task.progress_pct = progress_pct
            if target_status in ("succeeded", "failed", "partial_failed", "canceled"):
                task.finished_at = utcnow()

            db.commit()

    def dispatch(
        self,
        task_id: str,
        executor_func: Callable[[str, asyncio.Event], Coroutine[Any, Any, None]],
    ) -> None:
        """将任务投入异步有界并发队列并立即返回。"""
        cancel_event = asyncio.Event()
        self._cancel_events[task_id] = cancel_event

        async def _runner():
            with self.session_factory() as db:
                task = db.query(AiTask).filter(AiTask.id == task_id).first()
                provider_id = task.provider_id if task else None

            prov_sem = self._get_provider_semaphore(provider_id)
            async with self._semaphore:
                async with prov_sem:
                    # 检查运行前是否已取消
                    if cancel_event.is_set():
                        self.update_task_status(task_id, "canceled")
                        return

                    self.update_task_status(task_id, "running")
                    try:
                        await executor_func(task_id, cancel_event)
                    except asyncio.CancelledError:
                        self.update_task_status(task_id, "canceled")
                    except Exception as exc:
                        logger.exception(f"AI task {task_id} failed with error: {exc}")
                        self.update_task_status(
                            task_id,
                            "failed",
                            error_code="execution_error",
                            error_message=str(exc),
                        )
                    finally:
                        self._running_tasks.pop(task_id, None)
                        self._cancel_events.pop(task_id, None)

        try:
            loop = asyncio.get_running_loop()
            coro_task = loop.create_task(_runner())
            self._running_tasks[task_id] = coro_task
        except RuntimeError:
            # 当前线程没有 running event loop（例如在 FastAPI 线程池中调用）
            loop = self._loop
            if loop and loop.is_running():
                future = asyncio.run_coroutine_threadsafe(_runner(), loop)
            else:
                import threading

                def _bg_run():
                    asyncio.run(_runner())

                t = threading.Thread(target=_bg_run, daemon=True)
                t.start()

    def request_cancel(self, task_id: str) -> bool:
        """用户发起任务取消请求。"""
        with self.session_factory() as db:
            task = db.query(AiTask).filter(AiTask.id == task_id).first()
            if not task:
                raise ApiError(code="task_not_found", message=f"任务 #{task_id} 不存在", status_code=404)

            if task.status in ("succeeded", "failed", "partial_failed", "canceled"):
                return False  # 已处于终态

            if task.status == "queued":
                task.status = "canceled"
                task.finished_at = utcnow()
                db.commit()
                event = self._cancel_events.get(task_id)
                if event:
                    event.set()
                return True

            if task.status == "running":
                task.status = "cancel_requested"
                db.commit()
                event = self._cancel_events.get(task_id)
                if event:
                    event.set()
                # 同时触发底层协程取消
                coro = self._running_tasks.get(task_id)
                if coro and not coro.done():
                    coro.cancel()
                return True

            return False

    def retry_task(self, db: Session, task_id: str) -> AiTask:
        """为失败/取消/中断的任务创建带 retry_of 的新任务记录并返回。"""
        original = db.query(AiTask).filter(AiTask.id == task_id).first()
        if not original:
            raise ApiError(code="task_not_found", message=f"原任务 #{task_id} 不存在", status_code=404)

        if original.status in ("queued", "running"):
            raise ApiError(
                code="task_still_active",
                message=f"任务 #{task_id} 正在执行或排队中，无法重试",
                status_code=400,
            )

        # 兼容性与可用性校验：检查 Provider 与模型是否有效且已启用
        if original.model_profile_id:
            from backend.app.models.ai.model_config import AiModelProfile
            profile = db.get(AiModelProfile, original.model_profile_id)
            if not profile or not profile.enabled:
                raise ApiError(
                    code="model_unavailable",
                    message="原任务所使用的模型不存在或已被禁用，无法直接重试。建议使用‘生成变体’切换可用模型。",
                    status_code=400,
                )
            if profile.provider and not profile.provider.enabled:
                raise ApiError(
                    code="provider_unavailable",
                    message="原任务所使用的服务商处于禁用状态，无法直接重试。",
                    status_code=400,
                )

        new_task_id = f"aitask_{uuid.uuid4().hex[:16]}"
        new_task = AiTask(
            id=new_task_id,
            task_type=original.task_type,
            provider_id=original.provider_id,
            model_profile_id=original.model_profile_id,
            preset_id=original.preset_id,
            status="queued",
            prompt_final=original.prompt_final,
            raw_user_request=original.raw_user_request,
            params_json=original.params_json,
            retry_of=original.id,
        )
        db.add(new_task)
        db.flush()

        # 复制不可变输入快照引用
        for ref in original.references:
            new_ref = AiTaskReference(
                task_id=new_task_id,
                seq=ref.seq,
                role=ref.role,
                source_kind=ref.source_kind,
                source_id=ref.source_id,
                snapshot_path=ref.snapshot_path,
                sha256=ref.sha256,
            )
            db.add(new_ref)

        db.commit()
        db.refresh(new_task)
        return new_task

    def recover_interrupted_tasks_on_startup(self) -> dict[str, int]:
        """系统启动时将未完成的运行中任务标记为 recovery_needed，未开始的排队任务标记为 canceled。"""
        with self.session_factory() as db:
            running_tasks = (
                db.query(AiTask)
                .filter(AiTask.status.in_(["running", "cancel_requested"]))
                .all()
            )
            running_count = len(running_tasks)
            now = utcnow()
            for t in running_tasks:
                t.status = "recovery_needed"
                t.error_code = "process_interrupted"
                t.error_message = "服务进程重启或异常退出，上游执行状态未知，已转入待核验状态，避免盲目重复扣费"
                t.finished_at = now

            queued_tasks = (
                db.query(AiTask)
                .filter(AiTask.status == "queued")
                .all()
            )
            queued_count = len(queued_tasks)
            for t in queued_tasks:
                t.status = "canceled"
                t.error_code = "server_restarted"
                t.error_message = "系统重启，排队中的任务已自动取消"
                t.finished_at = now

            db.commit()
            if running_count > 0 or queued_count > 0:
                logger.info(
                    f"Recovered tasks on startup: {running_count} marked recovery_needed, {queued_count} marked canceled"
                )
            return {"recovery_needed": running_count, "canceled": queued_count}


_scheduler_instance: AiTaskScheduler | None = None


def get_task_scheduler() -> AiTaskScheduler:
    if _scheduler_instance is None:
        raise RuntimeError("AiTaskScheduler is not initialized.")
    return _scheduler_instance


def set_task_scheduler(scheduler: AiTaskScheduler | None) -> None:
    global _scheduler_instance
    _scheduler_instance = scheduler


def init_task_scheduler(
    session_factory: sessionmaker,
    max_global_concurrency: int = 3,
    per_provider_concurrency: int = 2,
) -> AiTaskScheduler:
    global _scheduler_instance
    _scheduler_instance = AiTaskScheduler(
        session_factory=session_factory,
        max_global_concurrency=max_global_concurrency,
        per_provider_concurrency=per_provider_concurrency,
    )
    _scheduler_instance.recover_interrupted_tasks_on_startup()
    return _scheduler_instance

