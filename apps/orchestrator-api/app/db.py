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
    from app.models.recovery_rule import RecoveryEventRule, RecoveryEventRuleState  # noqa: F401
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
                WHERE e.enumlabel IN ('db_backupper', 's3_backupper', 'db_restorer', 's3_restorer', 'env_backupper', 'env_restorer')
                GROUP BY t.typname
                ORDER BY COUNT(*) DESC, t.typname
                LIMIT 1
                """
            )
        ).scalar_one_or_none()

        if enum_type_name and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", enum_type_name):
            connection.execute(text(f"ALTER TYPE {enum_type_name} ADD VALUE IF NOT EXISTS 'env_synchronizer'"))
            connection.execute(text(f"ALTER TYPE {enum_type_name} ADD VALUE IF NOT EXISTS 'db_restorer'"))
            connection.execute(text(f"ALTER TYPE {enum_type_name} ADD VALUE IF NOT EXISTS 's3_restorer'"))
            connection.execute(text(f"ALTER TYPE {enum_type_name} ADD VALUE IF NOT EXISTS 'env_backupper'"))
            connection.execute(text(f"ALTER TYPE {enum_type_name} ADD VALUE IF NOT EXISTS 'env_restorer'"))

        connection.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS env_repository VARCHAR(255)"))
        connection.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS path_to_helmfile VARCHAR(255)"))
        connection.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS target_s3_aws_bucket_subfolder_name VARCHAR(255)"))
        connection.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS env_backups_filename_prefix VARCHAR(120)"))
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
                    namespace VARCHAR(120) NOT NULL DEFAULT 'default',
                    db_display_name VARCHAR(120) NOT NULL DEFAULT 'DB backup',
                    s3_display_name VARCHAR(120) NOT NULL DEFAULT 'S3 backup',
                    enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    db_task_id INTEGER NULL REFERENCES tasks(id),
                    s3_task_id INTEGER NULL REFERENCES tasks(id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(text("ALTER TABLE backup_event_rules ADD COLUMN IF NOT EXISTS namespace VARCHAR(120) NOT NULL DEFAULT 'default'"))
        connection.execute(text("ALTER TABLE backup_event_rules ADD COLUMN IF NOT EXISTS db_display_name VARCHAR(120) NOT NULL DEFAULT 'DB backup'"))
        connection.execute(text("ALTER TABLE backup_event_rules ADD COLUMN IF NOT EXISTS s3_display_name VARCHAR(120) NOT NULL DEFAULT 'S3 backup'"))
        connection.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS managed_by_rule_id INTEGER NULL"))
        connection.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS managed_by_recovery_rule_id INTEGER NULL"))
        connection.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'fk_tasks_managed_by_rule_id'
                    ) THEN
                        ALTER TABLE tasks
                        ADD CONSTRAINT fk_tasks_managed_by_rule_id
                        FOREIGN KEY (managed_by_rule_id) REFERENCES backup_event_rules(id);
                    END IF;
                END$$
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
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS recovery_event_rules (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(120) NOT NULL UNIQUE,
                    namespace VARCHAR(120) NOT NULL DEFAULT 'default',
                    db_display_name VARCHAR(120) NOT NULL DEFAULT 'DB restore',
                    s3_display_name VARCHAR(120) NOT NULL DEFAULT 'S3 restore',
                    enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    db_task_id INTEGER NULL REFERENCES tasks(id),
                    s3_task_id INTEGER NULL REFERENCES tasks(id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS recovery_event_rule_states (
                    rule_id INTEGER PRIMARY KEY REFERENCES recovery_event_rules(id),
                    last_db_is_empty BOOLEAN NOT NULL DEFAULT FALSE,
                    last_s3_is_empty BOOLEAN NOT NULL DEFAULT FALSE,
                    last_db_had_data BOOLEAN NOT NULL DEFAULT FALSE,
                    last_s3_had_data BOOLEAN NOT NULL DEFAULT FALSE,
                    db_restore_pending BOOLEAN NOT NULL DEFAULT FALSE,
                    s3_restore_pending BOOLEAN NOT NULL DEFAULT FALSE,
                    last_polled_at TIMESTAMPTZ NULL,
                    last_db_empty_at TIMESTAMPTZ NULL,
                    last_s3_empty_at TIMESTAMPTZ NULL,
                    last_db_triggered_at TIMESTAMPTZ NULL,
                    last_s3_triggered_at TIMESTAMPTZ NULL,
                    last_error_at TIMESTAMPTZ NULL,
                    last_error_message TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(text("ALTER TABLE recovery_event_rule_states ADD COLUMN IF NOT EXISTS last_db_had_data BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE recovery_event_rule_states ADD COLUMN IF NOT EXISTS last_s3_had_data BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'fk_tasks_managed_by_recovery_rule_id'
                    ) THEN
                        ALTER TABLE tasks
                        ADD CONSTRAINT fk_tasks_managed_by_recovery_rule_id
                        FOREIGN KEY (managed_by_recovery_rule_id) REFERENCES recovery_event_rules(id);
                    END IF;
                END$$
                """
            )
        )
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_backup_event_rules_db_task_id ON backup_event_rules(db_task_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_backup_event_rules_s3_task_id ON backup_event_rules(s3_task_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_managed_by_rule_id ON tasks(managed_by_rule_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_recovery_event_rules_db_task_id ON recovery_event_rules(db_task_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_recovery_event_rules_s3_task_id ON recovery_event_rules(s3_task_id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_managed_by_recovery_rule_id ON tasks(managed_by_recovery_rule_id)"))
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
        connection.execute(
            text(
                """
                DELETE FROM backup_event_rule_states
                WHERE rule_id IN (
                    SELECT r.id
                    FROM backup_event_rules AS r
                    LEFT JOIN tasks AS db_task ON db_task.id = r.db_task_id
                    LEFT JOIN tasks AS s3_task ON s3_task.id = r.s3_task_id
                    WHERE COALESCE(db_task.managed_by_rule_id, s3_task.managed_by_rule_id) IS NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                DELETE FROM backup_event_rules AS r
                WHERE EXISTS (
                    SELECT 1
                    FROM tasks AS db_task
                    WHERE db_task.id = r.db_task_id
                      AND db_task.managed_by_rule_id IS NULL
                )
                   OR EXISTS (
                    SELECT 1
                    FROM tasks AS s3_task
                    WHERE s3_task.id = r.s3_task_id
                      AND s3_task.managed_by_rule_id IS NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                DELETE FROM recovery_event_rule_states
                WHERE rule_id IN (
                    SELECT r.id
                    FROM recovery_event_rules AS r
                    LEFT JOIN tasks AS db_task ON db_task.id = r.db_task_id
                    LEFT JOIN tasks AS s3_task ON s3_task.id = r.s3_task_id
                    WHERE COALESCE(db_task.managed_by_recovery_rule_id, s3_task.managed_by_recovery_rule_id) IS NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                DELETE FROM recovery_event_rules AS r
                WHERE EXISTS (
                    SELECT 1
                    FROM tasks AS db_task
                    WHERE db_task.id = r.db_task_id
                      AND db_task.managed_by_recovery_rule_id IS NULL
                )
                   OR EXISTS (
                    SELECT 1
                    FROM tasks AS s3_task
                    WHERE s3_task.id = r.s3_task_id
                      AND s3_task.managed_by_recovery_rule_id IS NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                DELETE FROM task_event_watch_states
                WHERE task_id IN (
                    SELECT id
                    FROM tasks
                    WHERE managed_by_rule_id IS NULL
                      AND managed_by_recovery_rule_id IS NULL
                      AND trigger_mode = 'event_based'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                DELETE FROM task_job_runs
                WHERE task_id IN (
                    SELECT id
                    FROM tasks
                    WHERE managed_by_rule_id IS NULL
                      AND managed_by_recovery_rule_id IS NULL
                      AND trigger_mode = 'event_based'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                DELETE FROM notifications
                WHERE task_id IN (
                    SELECT id
                    FROM tasks
                    WHERE managed_by_rule_id IS NULL
                      AND managed_by_recovery_rule_id IS NULL
                      AND trigger_mode = 'event_based'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                DELETE FROM tasks
                WHERE managed_by_rule_id IS NULL
                  AND managed_by_recovery_rule_id IS NULL
                  AND trigger_mode = 'event_based'
                """
            )
        )
