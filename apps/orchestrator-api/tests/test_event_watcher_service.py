from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import Settings
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
