from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ServiceType(str, enum.Enum):
    DB_BACKUPPER = "db_backupper"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(Enum(ServiceType), nullable=False, default=ServiceType.DB_BACKUPPER)
    namespace: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    schedule: Mapped[str] = mapped_column(String(120), nullable=False)
    db_backups_filename_prefix: Mapped[str] = mapped_column(String(120), nullable=False)
    database_host: Mapped[str] = mapped_column(String(255), nullable=False)
    database_name: Mapped[str] = mapped_column(String(120), nullable=False)
    database_username: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_aws_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_aws_bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_aws_access_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    release_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    last_apply_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_apply_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    secret: Mapped["TaskSecret"] = relationship(back_populates="task", uselist=False, cascade="all, delete-orphan")


class TaskSecret(Base):
    __tablename__ = "task_secrets"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    database_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped[Task] = relationship(back_populates="secret")
