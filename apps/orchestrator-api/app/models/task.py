from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ServiceType(str, enum.Enum):
    DB_BACKUPPER = "db_backupper"
    S3_BACKUPPER = "s3_backupper"
    DB_RESTORER = "db_restorer"
    S3_RESTORER = "s3_restorer"
    ENV_BACKUPPER = "env_backupper"
    ENV_SYNCHRONIZER = "env_synchronizer"


class TriggerMode(str, enum.Enum):
    SCHEDULED = "scheduled"
    EVENT_BASED = "event_based"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(Enum(ServiceType), nullable=False, default=ServiceType.DB_BACKUPPER)
    namespace: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    schedule: Mapped[str | None] = mapped_column(String(120), nullable=True)
    trigger_mode: Mapped[str] = mapped_column(String(20), nullable=False, default=TriggerMode.SCHEDULED.value)
    db_backups_filename_prefix: Mapped[str | None] = mapped_column(String(120), nullable=True)
    database_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    database_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    destination_aws_endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_aws_bucket_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    destination_aws_access_key_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_backups_filename_prefix: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_s3_aws_endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_s3_aws_access_key_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_s3_aws_bucket_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_s3_aws_bucket_subfolder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_s3_aws_endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_s3_aws_access_key_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_s3_aws_bucket_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_s3_aws_bucket_subfolder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    env_backups_filename_prefix: Mapped[str | None] = mapped_column(String(120), nullable=True)
    env_repository: Mapped[str | None] = mapped_column(String(255), nullable=True)
    path_to_helmfile: Mapped[str | None] = mapped_column(String(255), nullable=True)
    managed_by_rule_id: Mapped[int | None] = mapped_column(ForeignKey("backup_event_rules.id"), nullable=True, index=True)
    managed_by_recovery_rule_id: Mapped[int | None] = mapped_column(ForeignKey("recovery_event_rules.id"), nullable=True, index=True)
    release_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    last_apply_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_apply_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    secret: Mapped["TaskSecret"] = relationship(back_populates="task", uselist=False, cascade="all, delete-orphan")
    job_runs: Mapped[list["TaskJobRun"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    event_watch_state: Mapped["TaskEventWatchState | None"] = relationship(
        back_populates="task",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TaskSecret(Base):
    __tablename__ = "task_secrets"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    database_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_s3_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_s3_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped[Task] = relationship(back_populates="secret")


class TaskJobRun(Base):
    __tablename__ = "task_job_runs"
    __table_args__ = (
        UniqueConstraint("namespace", "job_name", name="uq_task_job_runs_namespace_job_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    namespace: Mapped[str] = mapped_column(String(120), nullable=False)
    release_name: Mapped[str] = mapped_column(String(120), nullable=False)
    job_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    logs_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    task: Mapped[Task] = relationship(back_populates="job_runs")


class TaskEventWatchState(Base):
    __tablename__ = "task_event_watch_states"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    last_tuple_ins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_tuple_upd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_tuple_del: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stats_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observed_state_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_change_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    task: Mapped[Task] = relationship(back_populates="event_watch_state")
