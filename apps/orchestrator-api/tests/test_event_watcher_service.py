from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.models.event_rule import BackupEventRule, BackupEventRuleDbConfig, BackupEventRuleS3Config
from app.models.runtime import DataChangeWatchState, WatchOwnerType
from app.models.task import DbBackupTaskConfig, S3BackupTaskConfig, ServiceType, Task, TriggerMode
from app.services.event_rule_service import EventRuleService
from app.services.event_watcher_service import DatabaseChangeCounters, EventWatcherService


class SessionFactory:
    def __init__(self, session) -> None:
        self.session = session

    def __call__(self):
        return self

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.session.expire_all()
        return False


def build_db_task() -> Task:
    task = Task(
        name="Primary DB",
        namespace="default",
        enabled=True,
        service_type=ServiceType.DB_BACKUPPER,
        schedule="0 * * * *",
        trigger_mode=TriggerMode.EVENT_BASED.value,
        release_name="db-backupper-1",
    )
    task.db_backup_config = DbBackupTaskConfig(
        db_backups_filename_prefix="primary",
        database_host="postgresql",
        database_name="app",
        database_username="postgres",
        database_password_encrypted="secret",
        destination_aws_endpoint="http://minio:9000",
        destination_aws_bucket_name="backups",
        destination_aws_access_key_id="minio",
        destination_aws_secret_access_key_encrypted="minio-secret",
    )
    return task


def build_s3_task() -> Task:
    task = Task(
        name="Bucket archive",
        namespace="default",
        enabled=True,
        service_type=ServiceType.S3_BACKUPPER,
        schedule=None,
        trigger_mode=TriggerMode.EVENT_BASED.value,
        release_name="s3-backupper-2",
        last_apply_status="deployed",
    )
    task.s3_backup_config = S3BackupTaskConfig(
        s3_backups_filename_prefix="bucket",
        source_s3_aws_endpoint="https://source.local",
        source_s3_aws_access_key_id="source-key",
        source_s3_aws_bucket_name="source-bucket",
        source_s3_aws_bucket_subfolder_name="incoming",
        source_s3_aws_secret_access_key_encrypted="source-secret",
        destination_s3_aws_endpoint="https://destination.local",
        destination_s3_aws_access_key_id="destination-key",
        destination_s3_aws_bucket_name="destination-bucket",
        destination_s3_aws_secret_access_key_encrypted="destination-secret",
    )
    return task


def get_task_state(db_session, task_id: int) -> DataChangeWatchState:
    return (
        db_session.query(DataChangeWatchState)
        .filter(DataChangeWatchState.owner_type == WatchOwnerType.TASK, DataChangeWatchState.owner_id == task_id)
        .one()
    )


def get_backup_rule_state(db_session, rule_id: int) -> DataChangeWatchState:
    return (
        db_session.query(DataChangeWatchState)
        .filter(DataChangeWatchState.owner_type == WatchOwnerType.BACKUP_RULE, DataChangeWatchState.owner_id == rule_id)
        .one()
    )


def test_standalone_event_based_backup_tasks_are_ignored(db_session, fake_kube, monkeypatch) -> None:
    task = build_db_task()
    db_session.add(task)
    db_session.commit()

    counters = iter(
        [
            DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(1, 0, 0, datetime(2026, 4, 13, tzinfo=timezone.utc)),
        ]
    )
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda config: next(counters)))

    service.poll_once()
    service.poll_once()

    state = (
        db_session.query(DataChangeWatchState)
        .filter(DataChangeWatchState.owner_type == WatchOwnerType.TASK, DataChangeWatchState.owner_id == task.id)
        .one_or_none()
    )
    assert state is None
    assert fake_kube.created_jobs == []


def build_combined_rule() -> BackupEventRule:
    rule = BackupEventRule(name="Combined backup", namespace="default", enabled=True)
    rule.db_config = BackupEventRuleDbConfig(
        name="Primary DB",
        db_backups_filename_prefix="primary",
        database_host="postgresql",
        database_name="app",
        database_username="postgres",
        database_password_encrypted="secret",
        destination_aws_endpoint="http://minio:9000",
        destination_aws_bucket_name="backups",
        destination_aws_access_key_id="minio",
        destination_aws_secret_access_key_encrypted="minio-secret",
    )
    rule.s3_config = BackupEventRuleS3Config(
        name="Bucket archive",
        s3_backups_filename_prefix="bucket",
        source_s3_aws_endpoint="https://source.local",
        source_s3_aws_access_key_id="source-key",
        source_s3_aws_bucket_name="source-bucket",
        source_s3_aws_bucket_subfolder_name="incoming",
        source_s3_aws_secret_access_key_encrypted="source-secret",
        destination_s3_aws_endpoint="https://destination.local",
        destination_s3_aws_access_key_id="destination-key",
        destination_s3_aws_bucket_name="destination-bucket",
        destination_s3_aws_secret_access_key_encrypted="destination-secret",
    )
    return rule


def test_combined_rule_first_poll_only_initializes_baselines(db_session, fake_kube, monkeypatch) -> None:
    rule = build_combined_rule()
    db_session.add(rule)
    db_session.commit()

    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(
        EventWatcherService,
        "_read_database_counters",
        staticmethod(lambda config: DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc))),
    )
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, config: "hash-1")

    service.poll_once()

    state = get_backup_rule_state(db_session, rule.id)
    assert state.last_tuple_ins == 10
    assert state.last_observed_state_hash == "hash-1"
    assert state.last_triggered_at is None
    assert fake_kube.created_jobs == []


def test_combined_rule_db_only_change_triggers_only_db_backup(db_session, fake_kube, monkeypatch) -> None:
    rule = build_combined_rule()
    db_session.add(rule)
    db_session.commit()

    counters = iter(
        [
            DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(11, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
        ]
    )
    s3_hashes = iter(["hash-1", "hash-1"])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda config: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, config: next(s3_hashes))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = get_backup_rule_state(db_session, rule.id)
    assert state.last_db_change_at is not None
    assert state.last_s3_change_at is None
    assert ("default", EventRuleService._db_release_name(rule.id), "event") in fake_kube.created_jobs
    assert ("default", EventRuleService._s3_release_name(rule.id), "event") not in fake_kube.created_jobs
    assert state.last_db_triggered_at is not None
    assert state.last_s3_triggered_at is None


def test_combined_rule_s3_only_change_triggers_only_s3_backup(db_session, fake_kube, monkeypatch) -> None:
    rule = build_combined_rule()
    db_session.add(rule)
    db_session.commit()

    counters = iter(
        [
            DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
        ]
    )
    s3_hashes = iter(["hash-1", "hash-2"])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda config: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, config: next(s3_hashes))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = get_backup_rule_state(db_session, rule.id)
    assert state.last_db_change_at is None
    assert state.last_s3_change_at is not None
    assert ("default", EventRuleService._db_release_name(rule.id), "event") not in fake_kube.created_jobs
    assert ("default", EventRuleService._s3_release_name(rule.id), "event") in fake_kube.created_jobs
    assert state.last_db_triggered_at is None
    assert state.last_s3_triggered_at is not None


def test_combined_rule_both_changes_in_same_poll_start_both_jobs(db_session, fake_kube, monkeypatch) -> None:
    rule = build_combined_rule()
    db_session.add(rule)
    db_session.commit()

    counters = iter(
        [
            DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(11, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
        ]
    )
    s3_hashes = iter(["hash-1", "hash-2"])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda config: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, config: next(s3_hashes))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = get_backup_rule_state(db_session, rule.id)
    assert ("default", EventRuleService._db_release_name(rule.id), "event") in fake_kube.created_jobs
    assert ("default", EventRuleService._s3_release_name(rule.id), "event") in fake_kube.created_jobs
    assert state.last_triggered_at is not None


def test_combined_rule_active_db_job_blocks_only_db_trigger(db_session, fake_kube, monkeypatch) -> None:
    rule = build_combined_rule()
    db_session.add(rule)
    db_session.commit()

    counters = iter(
        [
            DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(11, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
        ]
    )
    s3_hashes = iter(["hash-1", "hash-2"])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda config: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, config: next(s3_hashes))

    service.poll_once()
    fake_kube.jobs["default"] = [{"name": f"{EventRuleService._db_release_name(rule.id)}-event-001", "active": 1}]
    service.poll_once()

    assert ("default", EventRuleService._db_release_name(rule.id), "event") not in fake_kube.created_jobs
    assert ("default", EventRuleService._s3_release_name(rule.id), "event") in fake_kube.created_jobs


def test_combined_rule_component_cooldown_blocks_only_same_component(db_session, fake_kube, monkeypatch) -> None:
    rule = build_combined_rule()
    db_session.add(rule)
    db_session.commit()

    counters = iter(
        [
            DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(11, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(12, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
        ]
    )
    s3_hashes = iter(["hash-1", "hash-1", "hash-2"])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda config: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, config: next(s3_hashes))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = get_backup_rule_state(db_session, rule.id)
    assert ("default", EventRuleService._db_release_name(rule.id), "event") in fake_kube.created_jobs
    assert ("default", EventRuleService._s3_release_name(rule.id), "event") in fake_kube.created_jobs
    assert len(fake_kube.created_jobs) == 2


def test_combined_rule_failure_records_error(db_session, fake_kube, monkeypatch) -> None:
    rule = build_combined_rule()
    db_session.add(rule)
    db_session.commit()

    counters = iter(
        [
            DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(11, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
        ]
    )
    s3_hashes = iter(["hash-1", "hash-2"])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda config: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, config: next(s3_hashes))

    original_create_job = fake_kube.create_job

    def flaky_create_job(namespace: str, release_name: str, job_spec: dict, trigger_type: str = "manual") -> str:
        if release_name == EventRuleService._s3_release_name(rule.id):
            raise RuntimeError("boom")
        return original_create_job(namespace, release_name, job_spec, trigger_type)

    monkeypatch.setattr(fake_kube, "create_job", flaky_create_job)

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = get_backup_rule_state(db_session, rule.id)
    assert ("default", EventRuleService._db_release_name(rule.id), "event") in fake_kube.created_jobs
    assert state.last_error_message == "boom"
