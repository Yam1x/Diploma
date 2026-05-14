from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import boto3
import psycopg
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from psycopg import sql
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings, get_settings
from app.core.kube import KubeClient, KubernetesError
from app.db import SessionLocal
from app.models.event_rule import BackupEventRule
from app.models.recovery_rule import RecoveryEventRule
from app.models.runtime import DataChangeWatchState, EmptyStateWatchState, WatchOwnerType
from app.models.task import (
    DbBackupTaskConfig,
    DbRestoreTaskConfig,
    S3BackupTaskConfig,
    S3RestoreTaskConfig,
    ServiceType,
    Task,
    TriggerMode,
)
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
    def __init__(self, session_factory=SessionLocal, kube: KubeClient | None = None, settings: Settings | None = None) -> None:
        self.session_factory = session_factory
        self.kube = kube or KubeClient()
        self.settings = settings or get_settings()

    def run_forever(self) -> None:
        if not self.settings.event_watcher_enabled:
            logger.info("Event watcher is disabled")
            return
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
            backup_rules = self._load_backup_rules(db)
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

            for rule in backup_rules:
                try:
                    self._process_backup_rule(db, rule, jobs_by_namespace, event_rule_service)
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
        return (
            db.query(Task)
            .options(joinedload(Task.db_backup_config), joinedload(Task.s3_backup_config))
            .filter(
                Task.enabled.is_(True),
                Task.trigger_mode == TriggerMode.EVENT_BASED.value,
                Task.service_type.in_([ServiceType.DB_BACKUPPER, ServiceType.S3_BACKUPPER]),
            )
            .order_by(Task.id.asc())
            .all()
        )

    def _load_backup_rules(self, db: Session) -> list[BackupEventRule]:
        return (
            db.query(BackupEventRule)
            .options(joinedload(BackupEventRule.db_config), joinedload(BackupEventRule.s3_config))
            .filter(BackupEventRule.enabled.is_(True))
            .order_by(BackupEventRule.id.asc())
            .all()
        )

    def _load_recovery_rules(self, db: Session) -> list[RecoveryEventRule]:
        return (
            db.query(RecoveryEventRule)
            .options(joinedload(RecoveryEventRule.db_config), joinedload(RecoveryEventRule.s3_config))
            .filter(RecoveryEventRule.enabled.is_(True))
            .order_by(RecoveryEventRule.id.asc())
            .all()
        )

    def _process_task(self, db: Session, task: Task, jobs: list[dict], task_service: TaskService, notifications: NotificationService) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_data_watch_state(db, WatchOwnerType.TASK, task.id)
        state.last_polled_at = now
        state.last_error_message = None

        if task.service_type == ServiceType.DB_BACKUPPER:
            config = task.db_backup_config
            counters = self._read_database_counters(config)
            if self._should_rebaseline_db(state, counters):
                self._update_db_baseline(state, counters)
                return
            changed = self._has_counter_increase(state, counters)
            self._update_db_baseline(state, counters)
        else:
            config = task.s3_backup_config
            observed_state_hash = self._read_s3_state_hash(config)
            if state.last_observed_state_hash is None:
                state.last_observed_state_hash = observed_state_hash
                return
            changed = observed_state_hash != state.last_observed_state_hash
            state.last_observed_state_hash = observed_state_hash

        if changed:
            state.last_change_detected_at = now

        if not self._has_pending_change(state):
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
        state.last_triggered_at = now

    def _process_backup_rule(
        self,
        db: Session,
        rule: BackupEventRule,
        jobs_by_namespace: dict[str, list[dict]],
        service: EventRuleService,
    ) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_data_watch_state(db, WatchOwnerType.BACKUP_RULE, rule.id)
        state.last_polled_at = now
        state.last_error_message = None
        service._validate_rule(rule)

        counters = self._read_database_counters(rule.db_config)
        observed_state_hash = self._read_s3_state_hash(rule.s3_config)
        if self._should_rebaseline_db(state, counters) or state.last_observed_state_hash is None:
            self._update_db_baseline(state, counters)
            state.last_observed_state_hash = observed_state_hash
            return

        db_changed = self._has_counter_increase(state, counters)
        s3_changed = observed_state_hash != state.last_observed_state_hash
        self._update_db_baseline(state, counters)
        state.last_observed_state_hash = observed_state_hash
        if db_changed:
            state.last_db_change_at = now
        if s3_changed:
            state.last_s3_change_at = now
        if not db_changed or not s3_changed:
            return

        jobs = jobs_by_namespace.get(rule.namespace)
        if jobs is None:
            jobs = self.kube.list_jobs(rule.namespace)
            jobs_by_namespace[rule.namespace] = jobs
        if self._has_active_job(service._db_release_name(rule.id), jobs) or self._has_active_job(service._s3_release_name(rule.id), jobs):
            return
        if not self._cooldown_elapsed(state, now):
            return
        try:
            service._start_rule_jobs(rule, trigger_type="event")
        except HTTPException:
            return
        state.last_triggered_at = now

    def _process_recovery_rule(
        self,
        db: Session,
        rule: RecoveryEventRule,
        jobs_by_namespace: dict[str, list[dict]],
        service: RecoveryEventRuleService,
    ) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_empty_watch_state(db, rule.id)
        first_poll = state.last_polled_at is None
        state.last_polled_at = now
        state.last_error_message = None
        service._validate_rule(rule)

        db_is_empty = self._read_target_database_is_empty(rule.db_config)
        s3_is_empty = self._read_target_s3_is_empty(rule.s3_config)
        if first_poll:
            state.last_db_is_empty = db_is_empty
            state.last_s3_is_empty = s3_is_empty
            if db_is_empty:
                state.last_db_empty_at = now
            if s3_is_empty:
                state.last_s3_empty_at = now
            return

        db_became_empty = db_is_empty and not state.last_db_is_empty
        s3_became_empty = s3_is_empty and not state.last_s3_is_empty
        state.last_db_is_empty = db_is_empty
        state.last_s3_is_empty = s3_is_empty
        if db_became_empty:
            state.last_db_empty_at = now
        if s3_became_empty:
            state.last_s3_empty_at = now

        jobs = jobs_by_namespace.get(rule.namespace)
        if jobs is None:
            jobs = self.kube.list_jobs(rule.namespace)
            jobs_by_namespace[rule.namespace] = jobs

        if db_became_empty and not self._has_active_job(service._db_release_name(rule.id), jobs) and self._component_cooldown_elapsed(state.last_db_triggered_at, now):
            try:
                service._start_rule_jobs(rule, trigger_type="event", run_db=True, run_s3=False)
            except HTTPException:
                return
        if s3_became_empty and not self._has_active_job(service._s3_release_name(rule.id), jobs) and self._component_cooldown_elapsed(state.last_s3_triggered_at, now):
            try:
                service._start_rule_jobs(rule, trigger_type="event", run_db=False, run_s3=True)
            except HTTPException:
                return

    def _mark_task_error(self, db: Session, task: Task, notifications: NotificationService, message: str) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_data_watch_state(db, WatchOwnerType.TASK, task.id)
        state.last_polled_at = now
        state.last_error_at = now
        state.last_error_message = message
        notifications.notify_event_watcher_issue(task, message)

    @staticmethod
    def _ensure_data_watch_state(db: Session, owner_type: WatchOwnerType, owner_id: int) -> DataChangeWatchState:
        state = (
            db.query(DataChangeWatchState)
            .filter(DataChangeWatchState.owner_type == owner_type, DataChangeWatchState.owner_id == owner_id)
            .one_or_none()
        )
        if state is not None:
            return state
        state = DataChangeWatchState(owner_type=owner_type, owner_id=owner_id)
        db.add(state)
        db.flush()
        return state

    @staticmethod
    def _ensure_empty_watch_state(db: Session, rule_id: int) -> EmptyStateWatchState:
        state = (
            db.query(EmptyStateWatchState)
            .filter(EmptyStateWatchState.owner_type == WatchOwnerType.RECOVERY_RULE, EmptyStateWatchState.owner_id == rule_id)
            .one_or_none()
        )
        if state is not None:
            return state
        state = EmptyStateWatchState(owner_type=WatchOwnerType.RECOVERY_RULE, owner_id=rule_id)
        db.add(state)
        db.flush()
        return state

    @staticmethod
    def _should_rebaseline_db(state: DataChangeWatchState, counters: DatabaseChangeCounters) -> bool:
        if state.last_polled_at is None:
            return True
        if EventWatcherService._normalize_datetime(state.stats_reset_at) != EventWatcherService._normalize_datetime(counters.stats_reset_at):
            return True
        if state.last_tuple_ins is None or state.last_tuple_upd is None or state.last_tuple_del is None:
            return True
        return counters.tuple_ins < state.last_tuple_ins or counters.tuple_upd < state.last_tuple_upd or counters.tuple_del < state.last_tuple_del

    @staticmethod
    def _has_counter_increase(state: DataChangeWatchState, counters: DatabaseChangeCounters) -> bool:
        if state.last_tuple_ins is None or state.last_tuple_upd is None or state.last_tuple_del is None:
            return False
        return counters.tuple_ins > state.last_tuple_ins or counters.tuple_upd > state.last_tuple_upd or counters.tuple_del > state.last_tuple_del

    @staticmethod
    def _update_db_baseline(state: DataChangeWatchState, counters: DatabaseChangeCounters) -> None:
        state.last_tuple_ins = counters.tuple_ins
        state.last_tuple_upd = counters.tuple_upd
        state.last_tuple_del = counters.tuple_del
        state.stats_reset_at = counters.stats_reset_at

    @staticmethod
    def _has_pending_change(state: DataChangeWatchState) -> bool:
        return bool(state.last_change_detected_at and (state.last_triggered_at is None or state.last_change_detected_at > state.last_triggered_at))

    def _cooldown_elapsed(self, state: DataChangeWatchState, now: datetime) -> bool:
        last_triggered_at = self._normalize_datetime(state.last_triggered_at)
        return last_triggered_at is None or (now - last_triggered_at).total_seconds() >= self.settings.event_watcher_cooldown_seconds

    def _component_cooldown_elapsed(self, last_triggered_at: datetime | None, now: datetime) -> bool:
        normalized = self._normalize_datetime(last_triggered_at)
        return normalized is None or (now - normalized).total_seconds() >= self.settings.event_watcher_cooldown_seconds

    @staticmethod
    def _has_active_job(release_name: str, jobs: list[dict]) -> bool:
        prefix = f"{release_name}-"
        for job in jobs:
            name = str(job.get("name", ""))
            if name.startswith(prefix) and int(job.get("active", 0) or 0) > 0:
                return True
        return False

    @staticmethod
    def _read_database_counters(config: DbBackupTaskConfig) -> DatabaseChangeCounters:
        with psycopg.connect(
            host=config.database_host,
            dbname=config.database_name,
            user=config.database_username,
            password=config.database_password_encrypted,
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
        return DatabaseChangeCounters(int(row[0] or 0), int(row[1] or 0), int(row[2] or 0), stats_reset_at)

    def _read_s3_state_hash(self, config: S3BackupTaskConfig) -> str:
        client = boto3.client(
            "s3",
            endpoint_url=config.source_s3_aws_endpoint,
            aws_access_key_id=config.source_s3_aws_access_key_id,
            aws_secret_access_key=config.source_s3_aws_secret_access_key_encrypted,
            region_name=self.settings.minio_region,
            config=Config(signature_version="s3v4"),
        )
        continuation_token: str | None = None
        object_snapshots: list[dict[str, str | int | None]] = []
        prefix = (config.source_s3_aws_bucket_subfolder_name or "").strip()
        try:
            while True:
                params: dict[str, str | int] = {"Bucket": config.source_s3_aws_bucket_name, "Prefix": prefix, "MaxKeys": 1000}
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
        object_snapshots.sort(key=lambda item: (str(item["key"]), str(item["etag"] or ""), int(item["size"]), str(item["last_modified"] or "")))
        payload = json.dumps(object_snapshots, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _read_target_database_is_empty(config: DbRestoreTaskConfig) -> bool:
        with psycopg.connect(
            host=config.target_database_host,
            dbname=config.target_database_name,
            user=config.target_database_username,
            password=config.target_database_password_encrypted,
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
                    query = sql.SQL("SELECT EXISTS (SELECT 1 FROM {}.{} LIMIT 1)").format(sql.Identifier(table_schema), sql.Identifier(table_name))
                    cursor.execute(query)
                    row = cursor.fetchone()
                    if row and bool(row[0]):
                        return False
        return True

    def _read_target_s3_is_empty(self, config: S3RestoreTaskConfig) -> bool:
        client = boto3.client(
            "s3",
            endpoint_url=config.target_s3_aws_endpoint,
            aws_access_key_id=config.target_s3_aws_access_key_id,
            aws_secret_access_key=config.target_s3_aws_secret_access_key_encrypted,
            region_name=self.settings.minio_region,
            config=Config(signature_version="s3v4"),
        )
        prefix = (config.target_s3_aws_bucket_subfolder_name or "").strip()
        try:
            response = client.list_objects_v2(Bucket=config.target_s3_aws_bucket_name, Prefix=prefix, MaxKeys=1)
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Failed to read target S3 bucket state: {exc}") from exc
        return not bool(response.get("Contents"))

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)
