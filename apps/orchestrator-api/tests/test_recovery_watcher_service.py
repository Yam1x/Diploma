from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.models.recovery_rule import RecoveryEventRule, RecoveryEventRuleDbConfig, RecoveryEventRuleS3Config
from app.models.runtime import EmptyStateWatchState, WatchOwnerType
from app.services.event_watcher_service import EventWatcherService
from app.services.recovery_rule_service import RecoveryEventRuleService


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


def build_recovery_rule() -> RecoveryEventRule:
    rule = RecoveryEventRule(name="Combined recovery", namespace="default", enabled=True)
    rule.db_config = RecoveryEventRuleDbConfig(
        name="Primary DB restore",
        db_backups_filename_prefix="primary",
        source_aws_endpoint="http://minio:9000",
        source_aws_bucket_name="backups",
        source_aws_access_key_id="minio",
        source_aws_secret_access_key_encrypted="minio-secret",
        target_database_host="postgresql",
        target_database_name="app",
        target_database_username="postgres",
        target_database_password_encrypted="secret",
    )
    rule.s3_config = RecoveryEventRuleS3Config(
        name="Bucket restore",
        s3_backups_filename_prefix="bucket",
        source_s3_aws_endpoint="https://source.local",
        source_s3_aws_bucket_name="source-bucket",
        source_s3_aws_access_key_id="source-key",
        source_s3_aws_secret_access_key_encrypted="source-secret",
        target_s3_aws_endpoint="https://destination.local",
        target_s3_aws_bucket_name="destination-bucket",
        target_s3_aws_bucket_subfolder_name="incoming",
        target_s3_aws_access_key_id="destination-key",
        target_s3_aws_secret_access_key_encrypted="destination-secret",
    )
    return rule


def get_state(db_session, rule_id: int) -> EmptyStateWatchState:
    return (
        db_session.query(EmptyStateWatchState)
        .filter(EmptyStateWatchState.owner_type == WatchOwnerType.RECOVERY_RULE, EmptyStateWatchState.owner_id == rule_id)
        .one()
    )


def test_recovery_rule_first_poll_only_initializes_baseline(db_session, fake_kube, monkeypatch) -> None:
    rule = build_recovery_rule()
    db_session.add(rule)
    db_session.commit()

    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda config: True))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, config: False)

    service.poll_once()

    state = get_state(db_session, rule.id)
    assert state.last_db_is_empty is True
    assert state.last_s3_is_empty is False
    assert state.last_db_empty_at is not None
    assert state.last_s3_empty_at is None
    assert state.last_db_triggered_at is None
    assert state.last_s3_triggered_at is None
    assert fake_kube.created_jobs == []


def test_recovery_rule_always_empty_does_not_trigger_restore(db_session, fake_kube, monkeypatch) -> None:
    rule = build_recovery_rule()
    db_session.add(rule)
    db_session.commit()

    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda config: True))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, config: True)

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = get_state(db_session, rule.id)
    assert state.last_db_is_empty is True
    assert state.last_s3_is_empty is True
    assert state.last_db_triggered_at is None
    assert state.last_s3_triggered_at is None
    assert fake_kube.created_jobs == []


def test_recovery_rule_db_empty_triggers_only_db_restore(db_session, fake_kube, monkeypatch) -> None:
    rule = build_recovery_rule()
    db_session.add(rule)
    db_session.commit()

    db_values = iter([False, True])
    s3_values = iter([False, False])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda config: next(db_values)))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, config: next(s3_values))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = get_state(db_session, rule.id)
    assert ("default", RecoveryEventRuleService._db_release_name(rule.id), "event") in fake_kube.created_jobs
    assert ("default", RecoveryEventRuleService._s3_release_name(rule.id), "event") not in fake_kube.created_jobs
    assert state.last_db_triggered_at is not None
    assert state.last_s3_triggered_at is None


def test_recovery_rule_empty_after_seen_data_triggers_restore(db_session, fake_kube, monkeypatch) -> None:
    rule = build_recovery_rule()
    db_session.add(rule)
    db_session.commit()

    db_values = iter([True, False, True])
    s3_values = iter([True, False, True])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda config: next(db_values)))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, config: next(s3_values))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = get_state(db_session, rule.id)
    assert ("default", RecoveryEventRuleService._db_release_name(rule.id), "event") in fake_kube.created_jobs
    assert ("default", RecoveryEventRuleService._s3_release_name(rule.id), "event") in fake_kube.created_jobs
    assert state.last_db_empty_at is not None
    assert state.last_s3_empty_at is not None
    assert state.last_db_triggered_at is not None
    assert state.last_s3_triggered_at is not None


def test_recovery_rule_active_db_job_does_not_block_s3_restore(db_session, fake_kube, monkeypatch) -> None:
    rule = build_recovery_rule()
    db_session.add(rule)
    db_session.commit()

    db_values = iter([False, True])
    s3_values = iter([False, True])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda config: next(db_values)))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, config: next(s3_values))

    service.poll_once()
    fake_kube.jobs["default"] = [{"name": f"{RecoveryEventRuleService._db_release_name(rule.id)}-event-existing", "active": 1, "succeeded": 0, "failed": 0}]
    service.poll_once()

    state = get_state(db_session, rule.id)
    assert ("default", RecoveryEventRuleService._db_release_name(rule.id), "event") not in fake_kube.created_jobs
    assert ("default", RecoveryEventRuleService._s3_release_name(rule.id), "event") in fake_kube.created_jobs
    assert state.last_db_triggered_at is None
    assert state.last_s3_triggered_at is not None


def test_recovery_rule_does_not_retry_without_new_empty_transition(db_session, fake_kube, monkeypatch) -> None:
    rule = build_recovery_rule()
    db_session.add(rule)
    db_session.commit()

    db_values = iter([False, True, True])
    s3_values = iter([True, True, True])
    service = EventWatcherService(
        session_factory=SessionFactory(db_session),
        kube=fake_kube,
        settings=Settings(event_watcher_enabled=True, event_watcher_cooldown_seconds=600),
    )
    monkeypatch.setattr(EventWatcherService, "_read_target_database_is_empty", staticmethod(lambda config: next(db_values)))
    monkeypatch.setattr(EventWatcherService, "_read_target_s3_is_empty", lambda self, config: next(s3_values))

    service.poll_once()
    fake_kube.jobs["default"] = []
    service.poll_once()

    state = get_state(db_session, rule.id)
    state.last_db_triggered_at = datetime.now(timezone.utc) - timedelta(seconds=601)
    db_session.commit()

    fake_kube.jobs["default"] = []
    service.poll_once()

    db_session.refresh(state)
    assert len([item for item in fake_kube.created_jobs if item[1] == RecoveryEventRuleService._db_release_name(rule.id)]) == 1
