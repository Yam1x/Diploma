from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WatchOwnerType(str, enum.Enum):
    TASK = "task"
    BACKUP_RULE = "backup_rule"
    RECOVERY_RULE = "recovery_rule"


class RuleRunType(str, enum.Enum):
    BACKUP = "backup"
    RECOVERY = "recovery"


class RuleRunScope(str, enum.Enum):
    DB = "db"
    S3 = "s3"
    BOTH = "both"


class DataChangeWatchState(Base):
    __tablename__ = "data_change_watch_states"
    __table_args__ = (UniqueConstraint("owner_type", "owner_id", name="uq_data_change_watch_states_owner"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_type: Mapped[WatchOwnerType] = mapped_column(Enum(WatchOwnerType), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    last_tuple_ins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_tuple_upd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_tuple_del: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stats_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observed_state_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_change_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_db_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_s3_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EmptyStateWatchState(Base):
    __tablename__ = "empty_state_watch_states"
    __table_args__ = (UniqueConstraint("owner_type", "owner_id", name="uq_empty_state_watch_states_owner"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_type: Mapped[WatchOwnerType] = mapped_column(Enum(WatchOwnerType), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    last_db_is_empty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_s3_is_empty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_db_empty_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_s3_empty_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_db_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_s3_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RuleJobRun(Base):
    __tablename__ = "rule_job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_type: Mapped[RuleRunType] = mapped_column(Enum(RuleRunType), nullable=False)
    rule_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scope: Mapped[RuleRunScope] = mapped_column(Enum(RuleRunScope), nullable=False)
    namespace: Mapped[str] = mapped_column(String(120), nullable=False)
    db_release_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    s3_release_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    db_job_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_job_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    logs_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
