import re

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


settings = get_settings()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    from app.models.event_rule import BackupEventRule, BackupEventRuleState  # noqa: F401
    from app.models.notification import Notification  # noqa: F401
    from app.models.task import Task, TaskEventWatchState, TaskJobRun, TaskSecret  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _upgrade_task_schema()


def _upgrade_task_schema() -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as connection:
        enum_type_name = connection.execute(
            text(
                """
                SELECT t.typname
                FROM pg_type AS t
                JOIN pg_enum AS e ON e.enumtypid = t.oid
                WHERE e.enumlabel IN ('db_backupper', 's3_backupper')
                GROUP BY t.typname
                ORDER BY COUNT(*) DESC, t.typname
                LIMIT 1
                """
            )
        ).scalar_one_or_none()

        if enum_type_name and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", enum_type_name):
            connection.execute(text(f"ALTER TYPE {enum_type_name} ADD VALUE IF NOT EXISTS 'env_synchronizer'"))

        connection.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS env_repository VARCHAR(255)"))
        connection.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS path_to_helmfile VARCHAR(255)"))
        connection.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS trigger_mode VARCHAR(20) NOT NULL DEFAULT 'scheduled'"))
        connection.execute(text("ALTER TABLE tasks ALTER COLUMN schedule DROP NOT NULL"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS task_job_runs (
                    id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL REFERENCES tasks(id),
                    namespace VARCHAR(120) NOT NULL,
                    release_name VARCHAR(120) NOT NULL,
                    job_name VARCHAR(255) NOT NULL,
                    trigger_type VARCHAR(20) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'unknown',
                    started_at TIMESTAMPTZ NULL,
                    completed_at TIMESTAMPTZ NULL,
                    logs_text TEXT NULL,
                    logs_collected_at TIMESTAMPTZ NULL,
                    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_task_job_runs_namespace_job_name UNIQUE (namespace, job_name)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS task_event_watch_states (
                    task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
                    last_tuple_ins INTEGER NULL,
                    last_tuple_upd INTEGER NULL,
                    last_tuple_del INTEGER NULL,
                    stats_reset_at TIMESTAMPTZ NULL,
                    last_observed_state_hash TEXT NULL,
                    pending_change BOOLEAN NOT NULL DEFAULT FALSE,
                    last_polled_at TIMESTAMPTZ NULL,
                    last_change_detected_at TIMESTAMPTZ NULL,
                    last_event_triggered_at TIMESTAMPTZ NULL,
                    last_error_at TIMESTAMPTZ NULL,
                    last_error_message TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(text("ALTER TABLE task_event_watch_states ADD COLUMN IF NOT EXISTS last_observed_state_hash TEXT"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS backup_event_rules (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(120) NOT NULL UNIQUE,
                    enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    db_task_id INTEGER NOT NULL REFERENCES tasks(id),
                    s3_task_id INTEGER NOT NULL REFERENCES tasks(id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS backup_event_rule_states (
                    rule_id INTEGER PRIMARY KEY REFERENCES backup_event_rules(id),
                    last_tuple_ins INTEGER NULL,
                    last_tuple_upd INTEGER NULL,
                    last_tuple_del INTEGER NULL,
                    stats_reset_at TIMESTAMPTZ NULL,
                    last_observed_state_hash TEXT NULL,
                    last_polled_at TIMESTAMPTZ NULL,
                    last_db_change_at TIMESTAMPTZ NULL,
                    last_s3_change_at TIMESTAMPTZ NULL,
                    last_triggered_at TIMESTAMPTZ NULL,
                    last_error_at TIMESTAMPTZ NULL,
                    last_error_message TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_backup_event_rules_db_task_id ON backup_event_rules(db_task_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_backup_event_rules_s3_task_id ON backup_event_rules(s3_task_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_task_job_runs_task_id ON task_job_runs(task_id)"))
        connection.execute(text("ALTER TABLE task_job_runs ADD COLUMN IF NOT EXISTS logs_text TEXT"))
        connection.execute(text("ALTER TABLE task_job_runs ADD COLUMN IF NOT EXISTS logs_collected_at TIMESTAMPTZ"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    event_key VARCHAR(255) NOT NULL UNIQUE,
                    kind VARCHAR(64) NOT NULL,
                    severity VARCHAR(16) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    message TEXT NOT NULL,
                    task_id INTEGER NULL REFERENCES tasks(id),
                    job_run_id INTEGER NULL REFERENCES task_job_runs(id),
                    link_path VARCHAR(255) NULL,
                    is_read BOOLEAN NOT NULL DEFAULT FALSE,
                    read_at TIMESTAMPTZ NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_event_key ON notifications(event_key)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_task_id ON notifications(task_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_job_run_id ON notifications(job_run_id)"))
