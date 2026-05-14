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
    from app.models.event_rule import BackupEventRule, BackupEventRuleDbConfig, BackupEventRuleS3Config  # noqa: F401
    from app.models.notification import Notification  # noqa: F401
    from app.models.recovery_rule import RecoveryEventRule, RecoveryEventRuleDbConfig, RecoveryEventRuleS3Config  # noqa: F401
    from app.models.runtime import DataChangeWatchState, EmptyStateWatchState, RuleJobRun  # noqa: F401
    from app.models.task import (  # noqa: F401
        DbBackupTaskConfig,
        DbRestoreTaskConfig,
        EnvBackupTaskConfig,
        EnvRestoreTaskConfig,
        EnvSyncTaskConfig,
        S3BackupTaskConfig,
        S3RestoreTaskConfig,
        Task,
        TaskJobRun,
    )

    Base.metadata.create_all(bind=engine)
    _upgrade_task_schema()


def _upgrade_task_schema() -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as connection:
        def table_exists(table_name: str) -> bool:
            return bool(
                connection.execute(
                    text(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_schema = current_schema()
                              AND table_name = :table_name
                        )
                        """
                    ),
                    {"table_name": table_name},
                ).scalar_one()
            )

        def column_exists(table_name: str, column_name: str) -> bool:
            return bool(
                connection.execute(
                    text(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_schema = current_schema()
                              AND table_name = :table_name
                              AND column_name = :column_name
                        )
                        """
                    ),
                    {"table_name": table_name, "column_name": column_name},
                ).scalar_one()
            )

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
        if column_exists("notifications", "task_id"):
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_task_id ON notifications(task_id)"))
        if column_exists("notifications", "job_run_id"):
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_job_run_id ON notifications(job_run_id)"))

        legacy_backup_rule_links = column_exists("backup_event_rules", "db_task_id") and column_exists("backup_event_rules", "s3_task_id")
        legacy_recovery_rule_links = column_exists("recovery_event_rules", "db_task_id") and column_exists("recovery_event_rules", "s3_task_id")
        legacy_managed_task_links = column_exists("tasks", "managed_by_rule_id") and column_exists("tasks", "managed_by_recovery_rule_id")

        if legacy_backup_rule_links:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_backup_event_rules_db_task_id ON backup_event_rules(db_task_id)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_backup_event_rules_s3_task_id ON backup_event_rules(s3_task_id)"))
        if legacy_recovery_rule_links:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_recovery_event_rules_db_task_id ON recovery_event_rules(db_task_id)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_recovery_event_rules_s3_task_id ON recovery_event_rules(s3_task_id)"))
        if legacy_managed_task_links:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_managed_by_rule_id ON tasks(managed_by_rule_id)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_managed_by_recovery_rule_id ON tasks(managed_by_recovery_rule_id)"))

        if legacy_backup_rule_links and legacy_managed_task_links:
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
        if legacy_recovery_rule_links and legacy_managed_task_links:
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
        if legacy_managed_task_links and table_exists("task_event_watch_states"):
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
            if column_exists("notifications", "task_id"):
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
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS db_backup_task_configs (
                    task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
                    db_backups_filename_prefix VARCHAR(120) NOT NULL,
                    database_host VARCHAR(255) NOT NULL,
                    database_name VARCHAR(120) NOT NULL,
                    database_username VARCHAR(120) NOT NULL,
                    database_password_encrypted TEXT NULL,
                    destination_aws_endpoint VARCHAR(255) NOT NULL,
                    destination_aws_bucket_name VARCHAR(120) NOT NULL,
                    destination_aws_access_key_id VARCHAR(255) NOT NULL,
                    destination_aws_secret_access_key_encrypted TEXT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS s3_backup_task_configs (
                    task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
                    s3_backups_filename_prefix VARCHAR(120) NOT NULL,
                    source_s3_aws_endpoint VARCHAR(255) NOT NULL,
                    source_s3_aws_access_key_id VARCHAR(255) NOT NULL,
                    source_s3_aws_bucket_name VARCHAR(120) NOT NULL,
                    source_s3_aws_bucket_subfolder_name VARCHAR(255) NULL,
                    source_s3_aws_secret_access_key_encrypted TEXT NULL,
                    destination_s3_aws_endpoint VARCHAR(255) NOT NULL,
                    destination_s3_aws_access_key_id VARCHAR(255) NOT NULL,
                    destination_s3_aws_bucket_name VARCHAR(120) NOT NULL,
                    destination_s3_aws_secret_access_key_encrypted TEXT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS env_backup_task_configs (
                    task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
                    env_backups_filename_prefix VARCHAR(120) NOT NULL,
                    destination_aws_endpoint VARCHAR(255) NOT NULL,
                    destination_aws_bucket_name VARCHAR(120) NOT NULL,
                    destination_aws_access_key_id VARCHAR(255) NOT NULL,
                    destination_aws_secret_access_key_encrypted TEXT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS db_restore_task_configs (
                    task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
                    db_backups_filename_prefix VARCHAR(120) NOT NULL,
                    source_aws_endpoint VARCHAR(255) NOT NULL,
                    source_aws_bucket_name VARCHAR(120) NOT NULL,
                    source_aws_access_key_id VARCHAR(255) NOT NULL,
                    source_aws_secret_access_key_encrypted TEXT NULL,
                    target_database_host VARCHAR(255) NOT NULL,
                    target_database_name VARCHAR(120) NOT NULL,
                    target_database_username VARCHAR(120) NOT NULL,
                    target_database_password_encrypted TEXT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS s3_restore_task_configs (
                    task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
                    s3_backups_filename_prefix VARCHAR(120) NOT NULL,
                    source_s3_aws_endpoint VARCHAR(255) NOT NULL,
                    source_s3_aws_bucket_name VARCHAR(120) NOT NULL,
                    source_s3_aws_access_key_id VARCHAR(255) NOT NULL,
                    source_s3_aws_secret_access_key_encrypted TEXT NULL,
                    target_s3_aws_endpoint VARCHAR(255) NOT NULL,
                    target_s3_aws_bucket_name VARCHAR(120) NOT NULL,
                    target_s3_aws_bucket_subfolder_name VARCHAR(255) NULL,
                    target_s3_aws_access_key_id VARCHAR(255) NOT NULL,
                    target_s3_aws_secret_access_key_encrypted TEXT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS env_restore_task_configs (
                    task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
                    env_backups_filename_prefix VARCHAR(120) NOT NULL,
                    source_aws_endpoint VARCHAR(255) NOT NULL,
                    source_aws_bucket_name VARCHAR(120) NOT NULL,
                    source_aws_access_key_id VARCHAR(255) NOT NULL,
                    source_aws_secret_access_key_encrypted TEXT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS env_sync_task_configs (
                    task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
                    env_repository VARCHAR(255) NOT NULL,
                    path_to_helmfile VARCHAR(255) NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS backup_event_rule_db_configs (
                    rule_id INTEGER PRIMARY KEY REFERENCES backup_event_rules(id),
                    name VARCHAR(120) NOT NULL,
                    db_backups_filename_prefix VARCHAR(120) NOT NULL,
                    database_host VARCHAR(255) NOT NULL,
                    database_name VARCHAR(120) NOT NULL,
                    database_username VARCHAR(120) NOT NULL,
                    database_password_encrypted TEXT NULL,
                    destination_aws_endpoint VARCHAR(255) NOT NULL,
                    destination_aws_bucket_name VARCHAR(120) NOT NULL,
                    destination_aws_access_key_id VARCHAR(255) NOT NULL,
                    destination_aws_secret_access_key_encrypted TEXT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS backup_event_rule_s3_configs (
                    rule_id INTEGER PRIMARY KEY REFERENCES backup_event_rules(id),
                    name VARCHAR(120) NOT NULL,
                    s3_backups_filename_prefix VARCHAR(120) NOT NULL,
                    source_s3_aws_endpoint VARCHAR(255) NOT NULL,
                    source_s3_aws_access_key_id VARCHAR(255) NOT NULL,
                    source_s3_aws_bucket_name VARCHAR(120) NOT NULL,
                    source_s3_aws_bucket_subfolder_name VARCHAR(255) NULL,
                    source_s3_aws_secret_access_key_encrypted TEXT NULL,
                    destination_s3_aws_endpoint VARCHAR(255) NOT NULL,
                    destination_s3_aws_access_key_id VARCHAR(255) NOT NULL,
                    destination_s3_aws_bucket_name VARCHAR(120) NOT NULL,
                    destination_s3_aws_secret_access_key_encrypted TEXT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS recovery_event_rule_db_configs (
                    rule_id INTEGER PRIMARY KEY REFERENCES recovery_event_rules(id),
                    name VARCHAR(120) NOT NULL,
                    db_backups_filename_prefix VARCHAR(120) NOT NULL,
                    source_aws_endpoint VARCHAR(255) NOT NULL,
                    source_aws_bucket_name VARCHAR(120) NOT NULL,
                    source_aws_access_key_id VARCHAR(255) NOT NULL,
                    source_aws_secret_access_key_encrypted TEXT NULL,
                    target_database_host VARCHAR(255) NOT NULL,
                    target_database_name VARCHAR(120) NOT NULL,
                    target_database_username VARCHAR(120) NOT NULL,
                    target_database_password_encrypted TEXT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS recovery_event_rule_s3_configs (
                    rule_id INTEGER PRIMARY KEY REFERENCES recovery_event_rules(id),
                    name VARCHAR(120) NOT NULL,
                    s3_backups_filename_prefix VARCHAR(120) NOT NULL,
                    source_s3_aws_endpoint VARCHAR(255) NOT NULL,
                    source_s3_aws_bucket_name VARCHAR(120) NOT NULL,
                    source_s3_aws_access_key_id VARCHAR(255) NOT NULL,
                    source_s3_aws_secret_access_key_encrypted TEXT NULL,
                    target_s3_aws_endpoint VARCHAR(255) NOT NULL,
                    target_s3_aws_bucket_name VARCHAR(120) NOT NULL,
                    target_s3_aws_bucket_subfolder_name VARCHAR(255) NULL,
                    target_s3_aws_access_key_id VARCHAR(255) NOT NULL,
                    target_s3_aws_secret_access_key_encrypted TEXT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS data_change_watch_states (
                    id SERIAL PRIMARY KEY,
                    owner_type VARCHAR(32) NOT NULL,
                    owner_id INTEGER NOT NULL,
                    last_tuple_ins INTEGER NULL,
                    last_tuple_upd INTEGER NULL,
                    last_tuple_del INTEGER NULL,
                    stats_reset_at TIMESTAMPTZ NULL,
                    last_observed_state_hash TEXT NULL,
                    last_polled_at TIMESTAMPTZ NULL,
                    last_change_detected_at TIMESTAMPTZ NULL,
                    last_db_change_at TIMESTAMPTZ NULL,
                    last_s3_change_at TIMESTAMPTZ NULL,
                    last_triggered_at TIMESTAMPTZ NULL,
                    last_error_at TIMESTAMPTZ NULL,
                    last_error_message TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_data_change_watch_states_owner UNIQUE (owner_type, owner_id)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS empty_state_watch_states (
                    id SERIAL PRIMARY KEY,
                    owner_type VARCHAR(32) NOT NULL,
                    owner_id INTEGER NOT NULL,
                    last_db_is_empty BOOLEAN NOT NULL DEFAULT FALSE,
                    last_s3_is_empty BOOLEAN NOT NULL DEFAULT FALSE,
                    last_polled_at TIMESTAMPTZ NULL,
                    last_db_empty_at TIMESTAMPTZ NULL,
                    last_s3_empty_at TIMESTAMPTZ NULL,
                    last_db_triggered_at TIMESTAMPTZ NULL,
                    last_s3_triggered_at TIMESTAMPTZ NULL,
                    last_error_at TIMESTAMPTZ NULL,
                    last_error_message TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_empty_state_watch_states_owner UNIQUE (owner_type, owner_id)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS rule_job_runs (
                    id SERIAL PRIMARY KEY,
                    rule_type VARCHAR(32) NOT NULL,
                    rule_id INTEGER NOT NULL,
                    scope VARCHAR(16) NOT NULL,
                    namespace VARCHAR(120) NOT NULL,
                    db_release_name VARCHAR(120) NULL,
                    s3_release_name VARCHAR(120) NULL,
                    db_job_name VARCHAR(255) NULL,
                    s3_job_name VARCHAR(255) NULL,
                    trigger_type VARCHAR(20) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'unknown',
                    started_at TIMESTAMPTZ NULL,
                    completed_at TIMESTAMPTZ NULL,
                    logs_text TEXT NULL,
                    logs_collected_at TIMESTAMPTZ NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS resource_type VARCHAR(32)"))
        connection.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS resource_id INTEGER"))
        connection.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS run_type VARCHAR(32)"))
        connection.execute(text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS run_id INTEGER"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_resource_type ON notifications(resource_type)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_resource_id ON notifications(resource_id)"))
        legacy_task_config_backfill = table_exists("task_secrets") and column_exists("tasks", "db_backups_filename_prefix")
        if legacy_task_config_backfill:
            connection.execute(
                text(
                    """
                    INSERT INTO db_backup_task_configs (
                        task_id, db_backups_filename_prefix, database_host, database_name, database_username,
                        database_password_encrypted, destination_aws_endpoint, destination_aws_bucket_name,
                        destination_aws_access_key_id, destination_aws_secret_access_key_encrypted
                    )
                    SELECT
                        t.id, COALESCE(t.db_backups_filename_prefix, ''), COALESCE(t.database_host, ''), COALESCE(t.database_name, ''),
                        COALESCE(t.database_username, ''), s.database_password_encrypted, COALESCE(t.destination_aws_endpoint, ''),
                        COALESCE(t.destination_aws_bucket_name, ''), COALESCE(t.destination_aws_access_key_id, ''),
                        s.destination_aws_secret_access_key_encrypted
                    FROM tasks t
                    LEFT JOIN task_secrets s ON s.task_id = t.id
                    WHERE t.service_type::text = 'db_backupper'
                      AND NOT EXISTS (SELECT 1 FROM db_backup_task_configs c WHERE c.task_id = t.id)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO s3_backup_task_configs (
                        task_id, s3_backups_filename_prefix, source_s3_aws_endpoint, source_s3_aws_access_key_id,
                        source_s3_aws_bucket_name, source_s3_aws_bucket_subfolder_name, source_s3_aws_secret_access_key_encrypted,
                        destination_s3_aws_endpoint, destination_s3_aws_access_key_id, destination_s3_aws_bucket_name,
                        destination_s3_aws_secret_access_key_encrypted
                    )
                    SELECT
                        t.id, COALESCE(t.s3_backups_filename_prefix, ''), COALESCE(t.source_s3_aws_endpoint, ''),
                        COALESCE(t.source_s3_aws_access_key_id, ''), COALESCE(t.source_s3_aws_bucket_name, ''),
                        t.source_s3_aws_bucket_subfolder_name, s.source_s3_aws_secret_access_key_encrypted,
                        COALESCE(t.destination_s3_aws_endpoint, ''), COALESCE(t.destination_s3_aws_access_key_id, ''),
                        COALESCE(t.destination_s3_aws_bucket_name, ''), s.destination_s3_aws_secret_access_key_encrypted
                    FROM tasks t
                    LEFT JOIN task_secrets s ON s.task_id = t.id
                    WHERE t.service_type::text = 's3_backupper'
                      AND NOT EXISTS (SELECT 1 FROM s3_backup_task_configs c WHERE c.task_id = t.id)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO env_backup_task_configs (
                        task_id, env_backups_filename_prefix, destination_aws_endpoint, destination_aws_bucket_name,
                        destination_aws_access_key_id, destination_aws_secret_access_key_encrypted
                    )
                    SELECT
                        t.id, COALESCE(t.env_backups_filename_prefix, ''), COALESCE(t.destination_aws_endpoint, ''),
                        COALESCE(t.destination_aws_bucket_name, ''), COALESCE(t.destination_aws_access_key_id, ''),
                        s.destination_aws_secret_access_key_encrypted
                    FROM tasks t
                    LEFT JOIN task_secrets s ON s.task_id = t.id
                    WHERE t.service_type::text = 'env_backupper'
                      AND NOT EXISTS (SELECT 1 FROM env_backup_task_configs c WHERE c.task_id = t.id)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO db_restore_task_configs (
                        task_id, db_backups_filename_prefix, source_aws_endpoint, source_aws_bucket_name, source_aws_access_key_id,
                        source_aws_secret_access_key_encrypted, target_database_host, target_database_name, target_database_username,
                        target_database_password_encrypted
                    )
                    SELECT
                        t.id, COALESCE(t.db_backups_filename_prefix, ''), COALESCE(t.destination_aws_endpoint, ''),
                        COALESCE(t.destination_aws_bucket_name, ''), COALESCE(t.destination_aws_access_key_id, ''),
                        s.destination_aws_secret_access_key_encrypted, COALESCE(t.database_host, ''), COALESCE(t.database_name, ''),
                        COALESCE(t.database_username, ''), s.database_password_encrypted
                    FROM tasks t
                    LEFT JOIN task_secrets s ON s.task_id = t.id
                    WHERE t.service_type::text = 'db_restorer'
                      AND NOT EXISTS (SELECT 1 FROM db_restore_task_configs c WHERE c.task_id = t.id)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO s3_restore_task_configs (
                        task_id, s3_backups_filename_prefix, source_s3_aws_endpoint, source_s3_aws_bucket_name, source_s3_aws_access_key_id,
                        source_s3_aws_secret_access_key_encrypted, target_s3_aws_endpoint, target_s3_aws_bucket_name,
                        target_s3_aws_bucket_subfolder_name, target_s3_aws_access_key_id, target_s3_aws_secret_access_key_encrypted
                    )
                    SELECT
                        t.id, COALESCE(t.s3_backups_filename_prefix, ''), COALESCE(t.source_s3_aws_endpoint, ''),
                        COALESCE(t.source_s3_aws_bucket_name, ''), COALESCE(t.source_s3_aws_access_key_id, ''),
                        s.source_s3_aws_secret_access_key_encrypted, COALESCE(t.destination_s3_aws_endpoint, ''),
                        COALESCE(t.destination_s3_aws_bucket_name, ''), t.target_s3_aws_bucket_subfolder_name,
                        COALESCE(t.destination_s3_aws_access_key_id, ''), s.destination_s3_aws_secret_access_key_encrypted
                    FROM tasks t
                    LEFT JOIN task_secrets s ON s.task_id = t.id
                    WHERE t.service_type::text = 's3_restorer'
                      AND NOT EXISTS (SELECT 1 FROM s3_restore_task_configs c WHERE c.task_id = t.id)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO env_restore_task_configs (
                        task_id, env_backups_filename_prefix, source_aws_endpoint, source_aws_bucket_name, source_aws_access_key_id,
                        source_aws_secret_access_key_encrypted
                    )
                    SELECT
                        t.id, COALESCE(t.env_backups_filename_prefix, ''), COALESCE(t.destination_aws_endpoint, ''),
                        COALESCE(t.destination_aws_bucket_name, ''), COALESCE(t.destination_aws_access_key_id, ''),
                        s.destination_aws_secret_access_key_encrypted
                    FROM tasks t
                    LEFT JOIN task_secrets s ON s.task_id = t.id
                    WHERE t.service_type::text = 'env_restorer'
                      AND NOT EXISTS (SELECT 1 FROM env_restore_task_configs c WHERE c.task_id = t.id)
                    """
                )
            )
        connection.execute(
            text(
                """
                INSERT INTO env_sync_task_configs (task_id, env_repository, path_to_helmfile)
                SELECT t.id, COALESCE(t.env_repository, ''), COALESCE(t.path_to_helmfile, '')
                FROM tasks t
                WHERE t.service_type::text = 'env_synchronizer'
                  AND NOT EXISTS (SELECT 1 FROM env_sync_task_configs c WHERE c.task_id = t.id)
                """
            )
        )
        if legacy_task_config_backfill and legacy_backup_rule_links:
            connection.execute(
                text(
                    """
                    INSERT INTO backup_event_rule_db_configs (
                        rule_id, name, db_backups_filename_prefix, database_host, database_name, database_username,
                        database_password_encrypted, destination_aws_endpoint, destination_aws_bucket_name,
                        destination_aws_access_key_id, destination_aws_secret_access_key_encrypted
                    )
                    SELECT
                        r.id, COALESCE(r.db_display_name, 'DB backup'), COALESCE(t.db_backups_filename_prefix, ''),
                        COALESCE(t.database_host, ''), COALESCE(t.database_name, ''), COALESCE(t.database_username, ''),
                        s.database_password_encrypted, COALESCE(t.destination_aws_endpoint, ''), COALESCE(t.destination_aws_bucket_name, ''),
                        COALESCE(t.destination_aws_access_key_id, ''), s.destination_aws_secret_access_key_encrypted
                    FROM backup_event_rules r
                    JOIN tasks t ON t.id = r.db_task_id
                    LEFT JOIN task_secrets s ON s.task_id = t.id
                    WHERE NOT EXISTS (SELECT 1 FROM backup_event_rule_db_configs c WHERE c.rule_id = r.id)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO backup_event_rule_s3_configs (
                        rule_id, name, s3_backups_filename_prefix, source_s3_aws_endpoint, source_s3_aws_access_key_id,
                        source_s3_aws_bucket_name, source_s3_aws_bucket_subfolder_name, source_s3_aws_secret_access_key_encrypted,
                        destination_s3_aws_endpoint, destination_s3_aws_access_key_id, destination_s3_aws_bucket_name,
                        destination_s3_aws_secret_access_key_encrypted
                    )
                    SELECT
                        r.id, COALESCE(r.s3_display_name, 'S3 backup'), COALESCE(t.s3_backups_filename_prefix, ''),
                        COALESCE(t.source_s3_aws_endpoint, ''), COALESCE(t.source_s3_aws_access_key_id, ''),
                        COALESCE(t.source_s3_aws_bucket_name, ''), t.source_s3_aws_bucket_subfolder_name,
                        s.source_s3_aws_secret_access_key_encrypted, COALESCE(t.destination_s3_aws_endpoint, ''),
                        COALESCE(t.destination_s3_aws_access_key_id, ''), COALESCE(t.destination_s3_aws_bucket_name, ''),
                        s.destination_s3_aws_secret_access_key_encrypted
                    FROM backup_event_rules r
                    JOIN tasks t ON t.id = r.s3_task_id
                    LEFT JOIN task_secrets s ON s.task_id = t.id
                    WHERE NOT EXISTS (SELECT 1 FROM backup_event_rule_s3_configs c WHERE c.rule_id = r.id)
                    """
                )
            )
        if legacy_task_config_backfill and legacy_recovery_rule_links:
            connection.execute(
                text(
                    """
                    INSERT INTO recovery_event_rule_db_configs (
                        rule_id, name, db_backups_filename_prefix, source_aws_endpoint, source_aws_bucket_name, source_aws_access_key_id,
                        source_aws_secret_access_key_encrypted, target_database_host, target_database_name, target_database_username,
                        target_database_password_encrypted
                    )
                    SELECT
                        r.id, COALESCE(r.db_display_name, 'DB restore'), COALESCE(t.db_backups_filename_prefix, ''),
                        COALESCE(t.destination_aws_endpoint, ''), COALESCE(t.destination_aws_bucket_name, ''),
                        COALESCE(t.destination_aws_access_key_id, ''), s.destination_aws_secret_access_key_encrypted,
                        COALESCE(t.database_host, ''), COALESCE(t.database_name, ''), COALESCE(t.database_username, ''),
                        s.database_password_encrypted
                    FROM recovery_event_rules r
                    JOIN tasks t ON t.id = r.db_task_id
                    LEFT JOIN task_secrets s ON s.task_id = t.id
                    WHERE NOT EXISTS (SELECT 1 FROM recovery_event_rule_db_configs c WHERE c.rule_id = r.id)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO recovery_event_rule_s3_configs (
                        rule_id, name, s3_backups_filename_prefix, source_s3_aws_endpoint, source_s3_aws_bucket_name,
                        source_s3_aws_access_key_id, source_s3_aws_secret_access_key_encrypted, target_s3_aws_endpoint,
                        target_s3_aws_bucket_name, target_s3_aws_bucket_subfolder_name, target_s3_aws_access_key_id,
                        target_s3_aws_secret_access_key_encrypted
                    )
                    SELECT
                        r.id, COALESCE(r.s3_display_name, 'S3 restore'), COALESCE(t.s3_backups_filename_prefix, ''),
                        COALESCE(t.source_s3_aws_endpoint, ''), COALESCE(t.source_s3_aws_bucket_name, ''),
                        COALESCE(t.source_s3_aws_access_key_id, ''), s.source_s3_aws_secret_access_key_encrypted,
                        COALESCE(t.destination_s3_aws_endpoint, ''), COALESCE(t.destination_s3_aws_bucket_name, ''),
                        t.target_s3_aws_bucket_subfolder_name, COALESCE(t.destination_s3_aws_access_key_id, ''),
                        s.destination_s3_aws_secret_access_key_encrypted
                    FROM recovery_event_rules r
                    JOIN tasks t ON t.id = r.s3_task_id
                    LEFT JOIN task_secrets s ON s.task_id = t.id
                    WHERE NOT EXISTS (SELECT 1 FROM recovery_event_rule_s3_configs c WHERE c.rule_id = r.id)
                    """
                )
            )
        connection.execute(
            text(
                """
                INSERT INTO data_change_watch_states (
                    owner_type, owner_id, last_tuple_ins, last_tuple_upd, last_tuple_del, stats_reset_at,
                    last_observed_state_hash, last_polled_at, last_change_detected_at, last_triggered_at, last_error_at,
                    last_error_message
                )
                SELECT
                    'TASK', s.task_id, s.last_tuple_ins, s.last_tuple_upd, s.last_tuple_del, s.stats_reset_at,
                    s.last_observed_state_hash, s.last_polled_at, s.last_change_detected_at, s.last_event_triggered_at,
                    s.last_error_at, s.last_error_message
                FROM task_event_watch_states s
                WHERE NOT EXISTS (
                    SELECT 1 FROM data_change_watch_states d WHERE d.owner_type::text = 'TASK' AND d.owner_id = s.task_id
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO data_change_watch_states (
                    owner_type, owner_id, last_tuple_ins, last_tuple_upd, last_tuple_del, stats_reset_at,
                    last_observed_state_hash, last_polled_at, last_db_change_at, last_s3_change_at, last_triggered_at,
                    last_error_at, last_error_message
                )
                SELECT
                    'BACKUP_RULE', s.rule_id, s.last_tuple_ins, s.last_tuple_upd, s.last_tuple_del, s.stats_reset_at,
                    s.last_observed_state_hash, s.last_polled_at, s.last_db_change_at, s.last_s3_change_at,
                    s.last_triggered_at, s.last_error_at, s.last_error_message
                FROM backup_event_rule_states s
                WHERE NOT EXISTS (
                    SELECT 1 FROM data_change_watch_states d WHERE d.owner_type::text = 'BACKUP_RULE' AND d.owner_id = s.rule_id
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO empty_state_watch_states (
                    owner_type, owner_id, last_db_is_empty, last_s3_is_empty, last_polled_at, last_db_empty_at,
                    last_s3_empty_at, last_db_triggered_at, last_s3_triggered_at, last_error_at, last_error_message
                )
                SELECT
                    'RECOVERY_RULE', s.rule_id, s.last_db_is_empty, s.last_s3_is_empty, s.last_polled_at,
                    s.last_db_empty_at, s.last_s3_empty_at, s.last_db_triggered_at, s.last_s3_triggered_at,
                    s.last_error_at, s.last_error_message
                FROM recovery_event_rule_states s
                WHERE NOT EXISTS (
                    SELECT 1 FROM empty_state_watch_states d WHERE d.owner_type::text = 'RECOVERY_RULE' AND d.owner_id = s.rule_id
                )
                """
            )
        )
        if column_exists("notifications", "task_id") and column_exists("notifications", "job_run_id"):
            connection.execute(
                text(
                    """
                    UPDATE notifications
                    SET resource_type = CASE
                            WHEN task_id IS NOT NULL THEN 'task'
                            ELSE resource_type
                        END,
                        resource_id = COALESCE(resource_id, task_id),
                        run_type = CASE
                            WHEN job_run_id IS NOT NULL THEN 'task_job_run'
                            ELSE run_type
                        END,
                        run_id = COALESCE(run_id, job_run_id)
                    WHERE resource_type IS NULL OR resource_id IS NULL OR run_type IS NULL OR run_id IS NULL
                    """
                )
            )
