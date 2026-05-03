from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.models.recovery_rule import RecoveryEventRule, RecoveryEventRuleState
from app.models.task import ServiceType, Task, TaskSecret, TriggerMode
from app.services.event_watcher_service import EventWatcherService


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


def build_db_restore_task() -> Task:
    task = Task(
        name="Primary DB restore",
        namespace="default",
        enabled=True,
        service_type=ServiceType.DB_RESTORER,
        schedule=None,
        trigger_mode=TriggerMode.EVENT_BASED.value,
        release_name="db-restorer-1",
        db_backups_filename_prefix="primary",
        database_host="postgresql",
        database_name="app",
        database_username="postgres",
        destination_aws_endpoint="http://minio:9000",
        destination_aws_bucket_name="backups",
        destination_aws_access_key_id="minio",
        last_apply_status="deployed",
    )
    task.secret = TaskSecret(
        database_password_encrypted="secret",
        destination_aws_secret_access_key_encrypted="minio-secret",
    )
    return task


def build_s3_restore_task() -> Task:
    task = Task(
        name="Bucket restore",
        namespace="default",
        enabled=True,
        service_type=ServiceType.S3_RESTORER,
        schedule=None,
        trigger_mode=TriggerMode.EVENT_BASED.value,
        release_name="s3-restorer-2",
        s3_backups_filename_prefix="bucket",
        source_s3_aws_endpoint="https://source.local",
        source_s3_aws_access_key_id="source-key",
        source_s3_aws_bucket_name="source-bucket",
        destination_s3_aws_endpoint="https://destination.local",
        destination_s3_aws_access_key_id="destination-key",
        destination_s3_aws_bucket_name="destination-bucket",
        target_s3_aws_bucket_subfolder_name="incoming",
        last_apply_status="deployed",
    )
    task.secret = TaskSecret(
        source_s3_aws_secret_access_key_encrypted="source-secret",
        destination_s3_aws_secret_access_key_encrypted="destination-secret",
    )
    return task


def build_recovery_rule(db_task: Task, s3_task: Task) -> RecoveryEventRule:
    return RecoveryEventRule(
        name="Combined recovery",
        namespace="default",
        enabled=True,
        db_display_name="Primary DB restore",
        s3_display_name="Bucket restore",
        db_task=db_task,
        s3_task=s3_task,
    )


def attach_managed_task_links(rule: RecoveryEventRule) -> None:
    if rule.id is None:
        raise AssertionError("Recovery rule must be persisted before linking managed tasks")
    if rule.db_task is None or rule.s3_task is None:
        raise AssertionError("Recovery rule must have both managed tasks")
    rule.db_task.managed_by_recovery_rule_id = rule.id
    rule.s3_task.managed_by_recovery_rule_id = rule.id


def test_recovery_rule_first_poll_only_initializes_baseline(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_restore_task()
    s3_task = build_s3_restore_task()
    rule = build_recovery_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
    db_session.commit()
    attach_managed_task_links(rule)
    db_session.commit()

    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda task: True))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, task: False)

    service.poll_once()

    state = db_session.query(RecoveryEventRuleState).filter(RecoveryEventRuleState.rule_id == rule.id).one()
    assert state.last_db_is_empty is True
    assert state.last_s3_is_empty is False
    assert state.last_db_had_data is False
    assert state.last_s3_had_data is True
    assert state.last_db_triggered_at is None
    assert state.last_s3_triggered_at is None
    assert fake_kube.created_jobs == []


def test_recovery_rule_always_empty_does_not_trigger_restore(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_restore_task()
    s3_task = build_s3_restore_task()
    rule = build_recovery_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
    db_session.commit()
    attach_managed_task_links(rule)
    db_session.commit()

    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda task: True))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, task: True)

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = db_session.query(RecoveryEventRuleState).filter(RecoveryEventRuleState.rule_id == rule.id).one()
    assert state.last_db_had_data is False
    assert state.last_s3_had_data is False
    assert state.last_db_triggered_at is None
    assert state.last_s3_triggered_at is None
    assert fake_kube.created_jobs == []


def test_recovery_rule_db_empty_triggers_only_db_restore(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_restore_task()
    s3_task = build_s3_restore_task()
    rule = build_recovery_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
    db_session.commit()
    attach_managed_task_links(rule)
    db_session.commit()

    db_values = iter([False, True])
    s3_values = iter([False, False])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda task: next(db_values)))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, task: next(s3_values))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = db_session.query(RecoveryEventRuleState).filter(RecoveryEventRuleState.rule_id == rule.id).one()
    assert ("default", "db-restorer-1", "event") in fake_kube.created_jobs
    assert ("default", "s3-restorer-2", "event") not in fake_kube.created_jobs
    assert state.last_db_triggered_at is not None
    assert state.last_s3_triggered_at is None


def test_recovery_rule_empty_after_seen_data_triggers_restore(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_restore_task()
    s3_task = build_s3_restore_task()
    rule = build_recovery_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
    db_session.commit()
    attach_managed_task_links(rule)
    db_session.commit()

    db_values = iter([True, False, True])
    s3_values = iter([True, False, True])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda task: next(db_values)))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, task: next(s3_values))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = db_session.query(RecoveryEventRuleState).filter(RecoveryEventRuleState.rule_id == rule.id).one()
    assert ("default", "db-restorer-1", "event") in fake_kube.created_jobs
    assert ("default", "s3-restorer-2", "event") in fake_kube.created_jobs
    assert state.last_db_had_data is True
    assert state.last_s3_had_data is True
    assert state.last_db_triggered_at is not None
    assert state.last_s3_triggered_at is not None


def test_recovery_rule_active_db_job_does_not_block_s3_restore(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_restore_task()
    s3_task = build_s3_restore_task()
    rule = build_recovery_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
    db_session.commit()
    attach_managed_task_links(rule)
    db_session.commit()

    db_values = iter([False, True])
    s3_values = iter([False, True])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda task: next(db_values)))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, task: next(s3_values))

    service.poll_once()
    fake_kube.jobs["default"] = [{"name": "db-restorer-1-event-existing", "active": 1, "succeeded": 0, "failed": 0}]
    service.poll_once()

    state = db_session.query(RecoveryEventRuleState).filter(RecoveryEventRuleState.rule_id == rule.id).one()
    assert ("default", "db-restorer-1", "event") not in fake_kube.created_jobs
    assert ("default", "s3-restorer-2", "event") in fake_kube.created_jobs
    assert state.last_db_triggered_at is None
    assert state.last_s3_triggered_at is not None


def test_recovery_rule_retries_after_cooldown_while_still_empty(db_session, fake_kube, monkeypatch) -> None:
    db_task = build_db_restore_task()
    s3_task = build_s3_restore_task()
    rule = build_recovery_rule(db_task, s3_task)
    db_session.add_all([db_task, s3_task, rule])
    db_session.commit()
    attach_managed_task_links(rule)
    db_session.commit()

    db_values = iter([False, True, True])
    s3_values = iter([True, True, True])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda task: next(db_values)))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, task: next(s3_values))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = db_session.query(RecoveryEventRuleState).filter(RecoveryEventRuleState.rule_id == rule.id).one()
    state.last_db_triggered_at = datetime.now(timezone.utc) - timedelta(seconds=601)
    db_session.commit()

    fake_kube.jobs["default"] = []
    service.poll_once()

    db_session.refresh(state)
    assert len([item for item in fake_kube.created_jobs if item[1] == "db-restorer-1"]) == 2
