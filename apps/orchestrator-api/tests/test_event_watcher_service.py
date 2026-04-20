from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.models.event_rule import BackupEventRule, BackupEventRuleState
from app.models.task import ServiceType, Task, TaskEventWatchState, TaskSecret, TriggerMode
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
        db_backups_filename_prefix="primary",
        database_host="postgresql",
        database_name="app",
        database_username="postgres",
        destination_aws_endpoint="http://minio:9000",
        destination_aws_bucket_name="backups",
        destination_aws_access_key_id="minio",
    )
    task.secret = TaskSecret(
        database_password_encrypted="secret",
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
        s3_backups_filename_prefix="bucket",
        source_s3_aws_endpoint="https://source.local",
        source_s3_aws_access_key_id="source-key",
        source_s3_aws_bucket_name="source-bucket",
        source_s3_aws_bucket_subfolder_name="incoming",
        destination_s3_aws_endpoint="https://destination.local",
        destination_s3_aws_access_key_id="destination-key",
        destination_s3_aws_bucket_name="destination-bucket",
        last_apply_status="deployed",
    )
    task.secret = TaskSecret(
        source_s3_aws_secret_access_key_encrypted="source-secret",
        destination_s3_aws_secret_access_key_encrypted="destination-secret",
    )
    return task


def test_first_poll_only_initializes_baseline(db_session, fake_kube, monkeypatch) -> None:
    task = build_db_task()
    db_session.add(task)
    db_session.commit()

    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(
        EventWatcherService,
        "_read_database_counters",
        staticmethod(lambda task: DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc))),
    )

    service.poll_once()

    state = db_session.query(TaskEventWatchState).filter(TaskEventWatchState.task_id == task.id).one()
    assert state.last_tuple_ins == 10
    assert state.last_tuple_upd == 3
    assert state.last_tuple_del == 1
    assert state.pending_change is False
    assert fake_kube.created_jobs == []


def test_counter_growth_creates_event_job(db_session, fake_kube, monkeypatch) -> None:
    task = build_db_task()
    db_session.add(task)
    db_session.commit()

    counters = iter(
        [
            DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(11, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
        ]
    )
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda task: next(counters)))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = db_session.query(TaskEventWatchState).filter(TaskEventWatchState.task_id == task.id).one()
    assert fake_kube.created_jobs == [("default", "db-backupper-1", "event")]
    assert state.pending_change is False
    assert state.last_event_triggered_at is not None


def test_changes_during_cooldown_are_aggregated(db_session, fake_kube, monkeypatch) -> None:
    task = build_db_task()
    db_session.add(task)
    db_session.commit()

    counters = iter(
        [
            DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(11, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(12, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(12, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
        ]
    )
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda task: next(counters)))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()
    service.poll_once()

    state = db_session.query(TaskEventWatchState).filter(TaskEventWatchState.task_id == task.id).one()
    assert len(fake_kube.created_jobs) == 1
    assert state.pending_change is True

    state.last_event_triggered_at = datetime.now(timezone.utc) - timedelta(seconds=601)
    db_session.commit()
    fake_kube.jobs["default"] = []

    service.poll_once()

    db_session.refresh(state)
    assert len(fake_kube.created_jobs) == 2
    assert state.pending_change is False


def test_stats_reset_rebaselines_without_trigger(db_session, fake_kube, monkeypatch) -> None:
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
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda task: next(counters)))

    service.poll_once()
    service.poll_once()

    state = db_session.query(TaskEventWatchState).filter(TaskEventWatchState.task_id == task.id).one()
    assert state.last_tuple_ins == 1
    assert state.pending_change is False
    assert fake_kube.created_jobs == []


def build_combined_rule(db_task: Task, s3_task: Task) -> BackupEventRule:
    return BackupEventRule(
        name="Combined backup",
        enabled=True,
        db_task=db_task,
        s3_task=s3_task,
    )


def test_combined_rule_first_poll_only_initializes_baselines(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_task()
    db_task.last_apply_status = "deployed"
    s3_task = build_s3_task()
    rule = build_combined_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
    db_session.commit()

    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(
        EventWatcherService,
        "_read_database_counters",
        staticmethod(lambda task: DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc))),
    )
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, task: "hash-1")

    service.poll_once()

    state = db_session.query(BackupEventRuleState).filter(BackupEventRuleState.rule_id == rule.id).one()
    assert state.last_tuple_ins == 10
    assert state.last_observed_state_hash == "hash-1"
    assert state.last_triggered_at is None
    assert fake_kube.created_jobs == []


def test_combined_rule_db_only_change_does_not_trigger(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_task()
    db_task.last_apply_status = "deployed"
    s3_task = build_s3_task()
    rule = build_combined_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
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
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda task: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, task: next(s3_hashes))

    service.poll_once()
    service.poll_once()

    state = db_session.query(BackupEventRuleState).filter(BackupEventRuleState.rule_id == rule.id).one()
    assert state.last_db_change_at is not None
    assert state.last_s3_change_at is None
    assert fake_kube.created_jobs == []


def test_combined_rule_s3_only_change_does_not_trigger(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_task()
    db_task.last_apply_status = "deployed"
    s3_task = build_s3_task()
    rule = build_combined_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
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
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda task: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, task: next(s3_hashes))

    service.poll_once()
    service.poll_once()

    state = db_session.query(BackupEventRuleState).filter(BackupEventRuleState.rule_id == rule.id).one()
    assert state.last_db_change_at is None
    assert state.last_s3_change_at is not None
    assert fake_kube.created_jobs == []


def test_combined_rule_both_changes_in_same_poll_start_both_jobs(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_task()
    db_task.last_apply_status = "deployed"
    s3_task = build_s3_task()
    rule = build_combined_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
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
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda task: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, task: next(s3_hashes))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = db_session.query(BackupEventRuleState).filter(BackupEventRuleState.rule_id == rule.id).one()
    assert ("default", "db-backupper-1", "event") in fake_kube.created_jobs
    assert ("default", "s3-backupper-2", "event") in fake_kube.created_jobs
    assert state.last_triggered_at is not None


def test_combined_rule_active_job_blocks_trigger(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_task()
    db_task.last_apply_status = "deployed"
    s3_task = build_s3_task()
    rule = build_combined_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
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
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda task: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, task: next(s3_hashes))

    service.poll_once()
    fake_kube.jobs["default"] = [{"name": "db-backupper-1-event-001", "active": 1}]
    service.poll_once()

    assert fake_kube.created_jobs == []


def test_combined_rule_cooldown_blocks_repeated_trigger(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_task()
    db_task.last_apply_status = "deployed"
    s3_task = build_s3_task()
    rule = build_combined_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
    db_session.commit()

    counters = iter(
        [
            DatabaseChangeCounters(10, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(11, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(12, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
            DatabaseChangeCounters(13, 3, 1, datetime(2026, 4, 12, tzinfo=timezone.utc)),
        ]
    )
    s3_hashes = iter(["hash-1", "hash-2", "hash-3", "hash-4"])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda task: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, task: next(s3_hashes))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = db_session.query(BackupEventRuleState).filter(BackupEventRuleState.rule_id == rule.id).one()
    assert len(fake_kube.created_jobs) == 2
    first_triggered_at = state.last_triggered_at

    state.last_triggered_at = datetime.now(timezone.utc) - timedelta(seconds=601)
    db_session.commit()
    fake_kube.jobs["default"] = []

    service.poll_once()

    db_session.refresh(state)
    assert len(fake_kube.created_jobs) == 4
    assert state.last_triggered_at != first_triggered_at


def test_combined_rule_partial_failure_records_error(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_task()
    db_task.last_apply_status = "deployed"
    s3_task = build_s3_task()
    rule = build_combined_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
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
    monkeypatch.setattr(EventWatcherService, "_read_database_counters", staticmethod(lambda task: next(counters)))
    monkeypatch.setattr(EventWatcherService, "_read_s3_state_hash", lambda self, task: next(s3_hashes))

    original_create_job = fake_kube.create_job

    def flaky_create_job(namespace: str, release_name: str, job_spec: dict, trigger_type: str = "manual") -> str:
        if release_name == "s3-backupper-2":
            raise RuntimeError("boom")
        return original_create_job(namespace, release_name, job_spec, trigger_type)

    monkeypatch.setattr(fake_kube, "create_job", flaky_create_job)

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = db_session.query(BackupEventRuleState).filter(BackupEventRuleState.rule_id == rule.id).one()
    assert ("default", "db-backupper-1", "event") in fake_kube.created_jobs
    assert state.last_error_message is not None
    assert "partially started" in state.last_error_message
