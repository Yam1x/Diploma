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
    from app.models.task import Task, TaskSecret  # noqa: F401

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
