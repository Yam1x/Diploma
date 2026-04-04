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
    from app.models.task import Task, TaskJobRun, TaskSecret  # noqa: F401

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
                    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_task_job_runs_namespace_job_name UNIQUE (namespace, job_name)
                )
                """
            )
        )
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_task_job_runs_task_id ON task_job_runs(task_id)"))
