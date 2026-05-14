from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ServiceType(str, enum.Enum):
    DB_BACKUPPER = "db_backupper"
    S3_BACKUPPER = "s3_backupper"
    DB_RESTORER = "db_restorer"
    S3_RESTORER = "s3_restorer"
    ENV_BACKUPPER = "env_backupper"
    ENV_RESTORER = "env_restorer"
    ENV_SYNCHRONIZER = "env_synchronizer"


class TriggerMode(str, enum.Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT_BASED = "event_based"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(Enum(ServiceType), nullable=False, default=ServiceType.DB_BACKUPPER)
    namespace: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    schedule: Mapped[str | None] = mapped_column(String(120), nullable=True)
    trigger_mode: Mapped[str] = mapped_column(String(20), nullable=False, default=TriggerMode.SCHEDULED.value)
    release_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    last_apply_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_apply_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    db_backup_config: Mapped["DbBackupTaskConfig | None"] = relationship(back_populates="task", uselist=False, cascade="all, delete-orphan")
    s3_backup_config: Mapped["S3BackupTaskConfig | None"] = relationship(back_populates="task", uselist=False, cascade="all, delete-orphan")
    env_backup_config: Mapped["EnvBackupTaskConfig | None"] = relationship(back_populates="task", uselist=False, cascade="all, delete-orphan")
    db_restore_config: Mapped["DbRestoreTaskConfig | None"] = relationship(back_populates="task", uselist=False, cascade="all, delete-orphan")
    s3_restore_config: Mapped["S3RestoreTaskConfig | None"] = relationship(back_populates="task", uselist=False, cascade="all, delete-orphan")
    env_restore_config: Mapped["EnvRestoreTaskConfig | None"] = relationship(back_populates="task", uselist=False, cascade="all, delete-orphan")
    env_sync_config: Mapped["EnvSyncTaskConfig | None"] = relationship(back_populates="task", uselist=False, cascade="all, delete-orphan")
    job_runs: Mapped[list["TaskJobRun"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class DbBackupTaskConfig(Base):
    __tablename__ = "db_backup_task_configs"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    db_backups_filename_prefix: Mapped[str] = mapped_column(String(120), nullable=False)
    database_host: Mapped[str] = mapped_column(String(255), nullable=False)
    database_name: Mapped[str] = mapped_column(String(120), nullable=False)
    database_username: Mapped[str] = mapped_column(String(120), nullable=False)
    database_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_aws_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_aws_bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_aws_access_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped[Task] = relationship(back_populates="db_backup_config")


class S3BackupTaskConfig(Base):
    __tablename__ = "s3_backup_task_configs"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    s3_backups_filename_prefix: Mapped[str] = mapped_column(String(120), nullable=False)
    source_s3_aws_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    source_s3_aws_access_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_s3_aws_bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_s3_aws_bucket_subfolder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_s3_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_s3_aws_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_s3_aws_access_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_s3_aws_bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_s3_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped[Task] = relationship(back_populates="s3_backup_config")


class EnvBackupTaskConfig(Base):
    __tablename__ = "env_backup_task_configs"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    env_backups_filename_prefix: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_aws_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_aws_bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_aws_access_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped[Task] = relationship(back_populates="env_backup_config")


class DbRestoreTaskConfig(Base):
    __tablename__ = "db_restore_task_configs"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    db_backups_filename_prefix: Mapped[str] = mapped_column(String(120), nullable=False)
    source_aws_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    source_aws_bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_aws_access_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_database_host: Mapped[str] = mapped_column(String(255), nullable=False)
    target_database_name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_database_username: Mapped[str] = mapped_column(String(120), nullable=False)
    target_database_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped[Task] = relationship(back_populates="db_restore_config")


class S3RestoreTaskConfig(Base):
    __tablename__ = "s3_restore_task_configs"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    s3_backups_filename_prefix: Mapped[str] = mapped_column(String(120), nullable=False)
    source_s3_aws_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    source_s3_aws_bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_s3_aws_access_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_s3_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_s3_aws_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    target_s3_aws_bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_s3_aws_bucket_subfolder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_s3_aws_access_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    target_s3_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped[Task] = relationship(back_populates="s3_restore_config")


class EnvRestoreTaskConfig(Base):
    __tablename__ = "env_restore_task_configs"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    env_backups_filename_prefix: Mapped[str] = mapped_column(String(120), nullable=False)
    source_aws_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    source_aws_bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_aws_access_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped[Task] = relationship(back_populates="env_restore_config")


class EnvSyncTaskConfig(Base):
    __tablename__ = "env_sync_task_configs"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    env_repository: Mapped[str] = mapped_column(String(255), nullable=False)
    path_to_helmfile: Mapped[str] = mapped_column(String(255), nullable=False)

    task: Mapped[Task] = relationship(back_populates="env_sync_config")


class TaskJobRun(Base):
    __tablename__ = "task_job_runs"
    __table_args__ = (UniqueConstraint("namespace", "job_name", name="uq_task_job_runs_namespace_job_name"),)

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
