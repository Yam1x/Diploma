from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings, get_settings
from app.core.kube import KubeClient, KubernetesError
from app.db import SessionLocal
from app.models.task import ServiceType, Task, TaskEventWatchState, TriggerMode
from app.services.notification_service import NotificationService
from app.services.task_service import TaskService


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatabaseChangeCounters:
    tuple_ins: int
    tuple_upd: int
    tuple_del: int
    stats_reset_at: datetime | None


class EventWatcherService:
    def __init__(
        self,
        session_factory=SessionLocal,
        kube: KubeClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.kube = kube or KubeClient()
        self.settings = settings or get_settings()

    def run_forever(self) -> None:
        if not self.settings.event_watcher_enabled:
            logger.info("Event watcher is disabled")
            return

        logger.info(
            "Starting event watcher with poll_interval=%ss cooldown=%ss",
            self.settings.event_watcher_poll_interval_seconds,
            self.settings.event_watcher_cooldown_seconds,
        )
        while True:
            try:
                self.poll_once()
            except Exception:
                logger.exception("Event watcher poll failed")
            time.sleep(self.settings.event_watcher_poll_interval_seconds)

    def poll_once(self) -> None:
        with self.session_factory() as db:
            notifications = NotificationService(db)
            task_service = TaskService(db=db, kube=self.kube, notifications=notifications)
            tasks = self._load_tasks(db)
            jobs_by_namespace: dict[str, list[dict]] = {}

            for task in tasks:
                try:
                    jobs = jobs_by_namespace.get(task.namespace)
                    if jobs is None:
                        jobs = self.kube.list_jobs(task.namespace)
                        jobs_by_namespace[task.namespace] = jobs
                    self._process_task(db, task, jobs, task_service, notifications)
                except KubernetesError as exc:
                    self._mark_task_error(db, task, notifications, f"Kubernetes error: {exc}")
                except Exception as exc:
                    self._mark_task_error(db, task, notifications, str(exc))

            db.commit()

    def _load_tasks(self, db: Session) -> list[Task]:
        return (
            db.query(Task)
            .options(joinedload(Task.secret), joinedload(Task.event_watch_state))
            .filter(
                Task.enabled.is_(True),
                Task.service_type == ServiceType.DB_BACKUPPER,
                Task.trigger_mode == TriggerMode.EVENT_BASED.value,
            )
            .order_by(Task.id.asc())
            .all()
        )

    def _process_task(
        self,
        db: Session,
        task: Task,
        jobs: list[dict],
        task_service: TaskService,
        notifications: NotificationService,
    ) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_state(db, task)
        counters = self._read_database_counters(task)

        state.last_polled_at = now
        state.last_error_message = None

        if self._should_rebaseline(state, counters):
            self._update_baseline(state, counters, pending_change=False)
            return

        changed = self._has_counter_increase(state, counters)
        self._update_baseline(state, counters, pending_change=state.pending_change)

        if changed:
            state.pending_change = True
            state.last_change_detected_at = now

        if not state.pending_change:
            return

        if self._has_active_job(task.release_name, jobs):
            return

        if not self._cooldown_elapsed(state, now):
            return

        try:
            task_service.create_event_job_run(task)
        except Exception as exc:
            self._mark_task_error(db, task, notifications, f"Failed to create event job: {exc}")
            return

        state.pending_change = False
        state.last_event_triggered_at = now

    def _mark_task_error(
        self,
        db: Session,
        task: Task,
        notifications: NotificationService,
        message: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_state(db, task)
        state.last_polled_at = now
        state.last_error_at = now
        state.last_error_message = message
        notifications.notify_event_watcher_issue(task, message)

    @staticmethod
    def _ensure_state(db: Session, task: Task) -> TaskEventWatchState:
        state = task.event_watch_state
        if state is not None:
            return state

        state = TaskEventWatchState(task=task)
        db.add(state)
        db.flush()
        return state

    @staticmethod
    def _should_rebaseline(state: TaskEventWatchState, counters: DatabaseChangeCounters) -> bool:
        if state.last_polled_at is None:
            return True
        if EventWatcherService._normalize_datetime(state.stats_reset_at) != EventWatcherService._normalize_datetime(counters.stats_reset_at):
            return True
        if state.last_tuple_ins is None or state.last_tuple_upd is None or state.last_tuple_del is None:
            return True
        return (
            counters.tuple_ins < state.last_tuple_ins
            or counters.tuple_upd < state.last_tuple_upd
            or counters.tuple_del < state.last_tuple_del
        )

    @staticmethod
    def _has_counter_increase(state: TaskEventWatchState, counters: DatabaseChangeCounters) -> bool:
        if state.last_tuple_ins is None or state.last_tuple_upd is None or state.last_tuple_del is None:
            return False
        return (
            counters.tuple_ins > state.last_tuple_ins
            or counters.tuple_upd > state.last_tuple_upd
            or counters.tuple_del > state.last_tuple_del
        )

    @staticmethod
    def _update_baseline(
        state: TaskEventWatchState,
        counters: DatabaseChangeCounters,
        *,
        pending_change: bool,
    ) -> None:
        state.last_tuple_ins = counters.tuple_ins
        state.last_tuple_upd = counters.tuple_upd
        state.last_tuple_del = counters.tuple_del
        state.stats_reset_at = counters.stats_reset_at
        state.pending_change = pending_change

    def _cooldown_elapsed(self, state: TaskEventWatchState, now: datetime) -> bool:
        last_triggered_at = self._normalize_datetime(state.last_event_triggered_at)
        if last_triggered_at is None:
            return True

        return (now - last_triggered_at).total_seconds() >= self.settings.event_watcher_cooldown_seconds

    @staticmethod
    def _has_active_job(release_name: str, jobs: list[dict]) -> bool:
        prefix = f"{release_name}-"
        for job in jobs:
            name = str(job.get("name", ""))
            if not name.startswith(prefix):
                continue
            if int(job.get("active", 0) or 0) > 0:
                return True
        return False

    @staticmethod
    def _read_database_counters(task: Task) -> DatabaseChangeCounters:
        password = task.secret.database_password_encrypted if task.secret else None
        if not task.database_host or not task.database_name or not task.database_username or not password:
            raise RuntimeError("Database connection settings are incomplete")

        with psycopg.connect(
            host=task.database_host,
            dbname=task.database_name,
            user=task.database_username,
            password=password,
            connect_timeout=10,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT tup_inserted, tup_updated, tup_deleted, stats_reset
                    FROM pg_stat_database
                    WHERE datname = current_database()
                    """
                )
                row = cursor.fetchone()

        if row is None:
            raise RuntimeError("pg_stat_database did not return statistics for current database")

        stats_reset_at = row[3]
        if isinstance(stats_reset_at, datetime) and stats_reset_at.tzinfo is None:
            stats_reset_at = stats_reset_at.replace(tzinfo=timezone.utc)

        return DatabaseChangeCounters(
            tuple_ins=int(row[0] or 0),
            tuple_upd=int(row[1] or 0),
            tuple_del=int(row[2] or 0),
            stats_reset_at=stats_reset_at,
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)
