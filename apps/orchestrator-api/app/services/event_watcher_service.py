from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import boto3
import psycopg
from psycopg import sql
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings, get_settings
from app.core.kube import KubeClient, KubernetesError
from app.db import SessionLocal
from app.models.event_rule import BackupEventRule, BackupEventRuleState
from app.models.recovery_rule import RecoveryEventRule, RecoveryEventRuleState
from app.models.task import ServiceType, Task, TaskEventWatchState, TriggerMode
from app.services.event_rule_service import EventRuleService
from app.services.notification_service import NotificationService
from app.services.recovery_rule_service import RecoveryEventRuleService
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
            event_rule_service = EventRuleService(db=db, notifications=notifications, task_service=task_service)
            recovery_rule_service = RecoveryEventRuleService(db=db, notifications=notifications, task_service=task_service)
            tasks = self._load_tasks(db)
            rules = self._load_rules(db)
            recovery_rules = self._load_recovery_rules(db)
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

            for rule in rules:
                try:
                    self._process_rule(db, rule, jobs_by_namespace, event_rule_service)
                except KubernetesError as exc:
                    event_rule_service.record_rule_error(rule, f"Kubernetes error: {exc}")
                except Exception as exc:
                    event_rule_service.record_rule_error(rule, str(exc))

            for rule in recovery_rules:
                try:
                    self._process_recovery_rule(db, rule, jobs_by_namespace, recovery_rule_service)
                except KubernetesError as exc:
                    recovery_rule_service.record_rule_error(rule, f"Kubernetes error: {exc}")
                except Exception as exc:
                    recovery_rule_service.record_rule_error(rule, str(exc))

            db.commit()

    def _load_tasks(self, db: Session) -> list[Task]:
        linked_task_ids = {
            task_id
            for db_task_id, s3_task_id in db.query(BackupEventRule.db_task_id, BackupEventRule.s3_task_id)
            .filter(BackupEventRule.enabled.is_(True))
            .all()
            for task_id in (db_task_id, s3_task_id)
        }
        query = (
            db.query(Task)
            .options(joinedload(Task.secret), joinedload(Task.event_watch_state))
            .filter(
                Task.enabled.is_(True),
                Task.managed_by_rule_id.is_(None),
                Task.managed_by_recovery_rule_id.is_(None),
                Task.service_type.in_([ServiceType.DB_BACKUPPER, ServiceType.S3_BACKUPPER]),
                Task.trigger_mode == TriggerMode.EVENT_BASED.value,
            )
            .order_by(Task.id.asc())
        )
        if linked_task_ids:
            query = query.filter(Task.id.notin_(linked_task_ids))

        return query.all()

    def _load_rules(self, db: Session) -> list[BackupEventRule]:
        return (
            db.query(BackupEventRule)
            .options(
                joinedload(BackupEventRule.db_task).joinedload(Task.secret),
                joinedload(BackupEventRule.db_task).joinedload(Task.event_watch_state),
                joinedload(BackupEventRule.s3_task).joinedload(Task.secret),
                joinedload(BackupEventRule.s3_task).joinedload(Task.event_watch_state),
                joinedload(BackupEventRule.state),
            )
            .filter(BackupEventRule.enabled.is_(True))
            .order_by(BackupEventRule.id.asc())
            .all()
        )

    def _load_recovery_rules(self, db: Session) -> list[RecoveryEventRule]:
        return (
            db.query(RecoveryEventRule)
            .options(
                joinedload(RecoveryEventRule.db_task).joinedload(Task.secret),
                joinedload(RecoveryEventRule.s3_task).joinedload(Task.secret),
                joinedload(RecoveryEventRule.state),
            )
            .filter(RecoveryEventRule.enabled.is_(True))
            .order_by(RecoveryEventRule.id.asc())
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
        state.last_polled_at = now
        state.last_error_message = None

        if task.service_type == ServiceType.DB_BACKUPPER:
            counters = self._read_database_counters(task)
            if self._should_rebaseline_db(state, counters):
                self._update_db_baseline(state, counters, pending_change=False)
                return

            changed = self._has_counter_increase(state, counters)
            self._update_db_baseline(state, counters, pending_change=state.pending_change)
        elif task.service_type == ServiceType.S3_BACKUPPER:
            observed_state_hash = self._read_s3_state_hash(task)
            if self._should_rebaseline_s3(state):
                state.last_observed_state_hash = observed_state_hash
                state.pending_change = False
                return

            changed = observed_state_hash != state.last_observed_state_hash
            state.last_observed_state_hash = observed_state_hash
        else:
            return

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

    def _process_rule(
        self,
        db: Session,
        rule: BackupEventRule,
        jobs_by_namespace: dict[str, list[dict]],
        event_rule_service: EventRuleService,
    ) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_rule_state(db, rule)
        state.last_polled_at = now
        state.last_error_message = None

        event_rule_service._validate_linked_tasks(rule)

        counters = self._read_database_counters(rule.db_task)
        observed_state_hash = self._read_s3_state_hash(rule.s3_task)

        if self._should_rebaseline_db(state, counters) or self._should_rebaseline_s3(state):
            self._update_rule_db_baseline(state, counters)
            state.last_observed_state_hash = observed_state_hash
            return

        db_changed = self._has_counter_increase(state, counters)
        s3_changed = observed_state_hash != state.last_observed_state_hash

        self._update_rule_db_baseline(state, counters)
        state.last_observed_state_hash = observed_state_hash

        if db_changed:
            state.last_db_change_at = now
        if s3_changed:
            state.last_s3_change_at = now

        if not db_changed or not s3_changed:
            return

        db_jobs = jobs_by_namespace.get(rule.db_task.namespace)
        if db_jobs is None:
            db_jobs = self.kube.list_jobs(rule.db_task.namespace)
            jobs_by_namespace[rule.db_task.namespace] = db_jobs

        s3_jobs = jobs_by_namespace.get(rule.s3_task.namespace)
        if s3_jobs is None:
            s3_jobs = self.kube.list_jobs(rule.s3_task.namespace)
            jobs_by_namespace[rule.s3_task.namespace] = s3_jobs

        if self._has_active_job(rule.db_task.release_name, db_jobs) or self._has_active_job(rule.s3_task.release_name, s3_jobs):
            return

        if not self._rule_cooldown_elapsed(state, now):
            return

        try:
            event_rule_service._start_rule_jobs(rule, trigger_type="event")
        except HTTPException:
            return

    def _process_recovery_rule(
        self,
        db: Session,
        rule: RecoveryEventRule,
        jobs_by_namespace: dict[str, list[dict]],
        recovery_rule_service: RecoveryEventRuleService,
    ) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_recovery_rule_state(db, rule)
        is_first_poll = state.last_polled_at is None
        state.last_polled_at = now
        state.last_error_message = None

        recovery_rule_service._validate_linked_tasks(rule)

        db_is_empty = self._read_target_database_is_empty(rule.db_task)
        s3_is_empty = self._read_target_s3_is_empty(rule.s3_task)

        if is_first_poll:
            state.last_db_is_empty = db_is_empty
            state.last_s3_is_empty = s3_is_empty
            state.last_db_had_data = not db_is_empty
            state.last_s3_had_data = not s3_is_empty
            state.db_restore_pending = False
            state.s3_restore_pending = False
            if db_is_empty:
                state.last_db_empty_at = now
            if s3_is_empty:
                state.last_s3_empty_at = now
            return

        if not db_is_empty:
            state.last_db_had_data = True
            state.db_restore_pending = False
        elif state.last_db_had_data:
            if not state.last_db_is_empty:
                state.last_db_empty_at = now
            state.db_restore_pending = True
        else:
            state.db_restore_pending = False

        if not s3_is_empty:
            state.last_s3_had_data = True
            state.s3_restore_pending = False
        elif state.last_s3_had_data:
            if not state.last_s3_is_empty:
                state.last_s3_empty_at = now
            state.s3_restore_pending = True
        else:
            state.s3_restore_pending = False

        state.last_db_is_empty = db_is_empty
        state.last_s3_is_empty = s3_is_empty

        db_jobs = jobs_by_namespace.get(rule.db_task.namespace)
        if db_jobs is None:
            db_jobs = self.kube.list_jobs(rule.db_task.namespace)
            jobs_by_namespace[rule.db_task.namespace] = db_jobs

        s3_jobs = jobs_by_namespace.get(rule.s3_task.namespace)
        if s3_jobs is None:
            s3_jobs = self.kube.list_jobs(rule.s3_task.namespace)
            jobs_by_namespace[rule.s3_task.namespace] = s3_jobs

        if (
            state.db_restore_pending
            and not self._has_active_job(rule.db_task.release_name, db_jobs)
            and self._recovery_component_cooldown_elapsed(state.last_db_triggered_at, now)
        ):
            try:
                recovery_rule_service._start_rule_jobs(rule, trigger_type="event", run_db=True, run_s3=False)
                state.db_restore_pending = False
            except HTTPException:
                return

        if (
            state.s3_restore_pending
            and not self._has_active_job(rule.s3_task.release_name, s3_jobs)
            and self._recovery_component_cooldown_elapsed(state.last_s3_triggered_at, now)
        ):
            try:
                recovery_rule_service._start_rule_jobs(rule, trigger_type="event", run_db=False, run_s3=True)
                state.s3_restore_pending = False
            except HTTPException:
                return

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
    def _ensure_rule_state(db: Session, rule: BackupEventRule) -> BackupEventRuleState:
        state = rule.state
        if state is not None:
            return state

        state = BackupEventRuleState(rule=rule)
        db.add(state)
        db.flush()
        return state

    @staticmethod
    def _ensure_recovery_rule_state(db: Session, rule: RecoveryEventRule) -> RecoveryEventRuleState:
        state = rule.state
        if state is not None:
            return state

        state = RecoveryEventRuleState(rule=rule)
        db.add(state)
        db.flush()
        return state

    @staticmethod
    def _should_rebaseline_db(state: TaskEventWatchState, counters: DatabaseChangeCounters) -> bool:
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
    def _should_rebaseline_s3(state: TaskEventWatchState) -> bool:
        return state.last_observed_state_hash is None

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
    def _update_db_baseline(
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

    @staticmethod
    def _update_rule_db_baseline(
        state: BackupEventRuleState,
        counters: DatabaseChangeCounters,
    ) -> None:
        state.last_tuple_ins = counters.tuple_ins
        state.last_tuple_upd = counters.tuple_upd
        state.last_tuple_del = counters.tuple_del
        state.stats_reset_at = counters.stats_reset_at

    def _cooldown_elapsed(self, state: TaskEventWatchState, now: datetime) -> bool:
        last_triggered_at = self._normalize_datetime(state.last_event_triggered_at)
        if last_triggered_at is None:
            return True

        return (now - last_triggered_at).total_seconds() >= self.settings.event_watcher_cooldown_seconds

    def _rule_cooldown_elapsed(self, state: BackupEventRuleState, now: datetime) -> bool:
        last_triggered_at = self._normalize_datetime(state.last_triggered_at)
        if last_triggered_at is None:
            return True

        return (now - last_triggered_at).total_seconds() >= self.settings.event_watcher_cooldown_seconds

    def _recovery_component_cooldown_elapsed(self, last_triggered_at: datetime | None, now: datetime) -> bool:
        normalized = self._normalize_datetime(last_triggered_at)
        if normalized is None:
            return True
        return (now - normalized).total_seconds() >= self.settings.event_watcher_cooldown_seconds

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

    def _read_s3_state_hash(self, task: Task) -> str:
        source_secret = task.secret.source_s3_aws_secret_access_key_encrypted if task.secret else None
        if not task.source_s3_aws_endpoint or not task.source_s3_aws_access_key_id or not source_secret or not task.source_s3_aws_bucket_name:
            raise RuntimeError("Source S3 connection settings are incomplete")

        client = boto3.client(
            "s3",
            endpoint_url=task.source_s3_aws_endpoint,
            aws_access_key_id=task.source_s3_aws_access_key_id,
            aws_secret_access_key=source_secret,
            region_name=self.settings.minio_region,
            config=Config(signature_version="s3v4"),
        )

        continuation_token: str | None = None
        object_snapshots: list[dict[str, str | int | None]] = []
        prefix = (task.source_s3_aws_bucket_subfolder_name or "").strip()

        try:
            while True:
                params = {
                    "Bucket": task.source_s3_aws_bucket_name,
                    "Prefix": prefix,
                    "MaxKeys": 1000,
                }
                if continuation_token:
                    params["ContinuationToken"] = continuation_token

                response = client.list_objects_v2(**params)
                for item in response.get("Contents", []):
                    key = item.get("Key")
                    if not key:
                        continue

                    last_modified = item.get("LastModified")
                    if isinstance(last_modified, datetime) and last_modified.tzinfo is None:
                        last_modified = last_modified.replace(tzinfo=timezone.utc)

                    object_snapshots.append(
                        {
                            "key": str(key),
                            "etag": (item.get("ETag") or "").strip('"') or None,
                            "size": int(item.get("Size", 0) or 0),
                            "last_modified": last_modified.isoformat() if isinstance(last_modified, datetime) else None,
                        }
                    )

                if not response.get("IsTruncated"):
                    break
                continuation_token = response.get("NextContinuationToken")
                if not continuation_token:
                    break
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Failed to read source S3 bucket state: {exc}") from exc

        object_snapshots.sort(
            key=lambda item: (
                str(item["key"]),
                str(item["etag"] or ""),
                int(item["size"]),
                str(item["last_modified"] or ""),
            )
        )
        payload = json.dumps(object_snapshots, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _read_target_database_is_empty(task: Task) -> bool:
        password = task.secret.database_password_encrypted if task.secret else None
        if not task.database_host or not task.database_name or not task.database_username or not password:
            raise RuntimeError("Target database connection settings are incomplete")

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
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_type = 'BASE TABLE'
                      AND table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY table_schema, table_name
                    """
                )
                tables = cursor.fetchall()

                for table_schema, table_name in tables:
                    query = sql.SQL("SELECT EXISTS (SELECT 1 FROM {}.{} LIMIT 1)").format(
                        sql.Identifier(table_schema),
                        sql.Identifier(table_name),
                    )
                    cursor.execute(query)
                    row = cursor.fetchone()
                    if row and bool(row[0]):
                        return False

        return True

    def _read_target_s3_is_empty(self, task: Task) -> bool:
        target_secret = task.secret.destination_s3_aws_secret_access_key_encrypted if task.secret else None
        if not task.destination_s3_aws_endpoint or not task.destination_s3_aws_access_key_id or not target_secret or not task.destination_s3_aws_bucket_name:
            raise RuntimeError("Target S3 connection settings are incomplete")

        client = boto3.client(
            "s3",
            endpoint_url=task.destination_s3_aws_endpoint,
            aws_access_key_id=task.destination_s3_aws_access_key_id,
            aws_secret_access_key=target_secret,
            region_name=self.settings.minio_region,
            config=Config(signature_version="s3v4"),
        )
        prefix = (task.target_s3_aws_bucket_subfolder_name or "").strip()

        try:
            response = client.list_objects_v2(
                Bucket=task.destination_s3_aws_bucket_name,
                Prefix=prefix,
                MaxKeys=1,
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Failed to read target S3 bucket state: {exc}") from exc

        return not bool(response.get("Contents"))

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)
