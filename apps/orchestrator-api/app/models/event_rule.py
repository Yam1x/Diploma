from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.task import Task


class BackupEventRule(Base):
    __tablename__ = "backup_event_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    db_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    s3_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    db_task: Mapped[Task] = relationship(Task, foreign_keys=[db_task_id])
    s3_task: Mapped[Task] = relationship(Task, foreign_keys=[s3_task_id])
    state: Mapped["BackupEventRuleState | None"] = relationship(
        back_populates="rule",
        uselist=False,
        cascade="all, delete-orphan",
    )


class BackupEventRuleState(Base):
    __tablename__ = "backup_event_rule_states"

    rule_id: Mapped[int] = mapped_column(ForeignKey("backup_event_rules.id"), primary_key=True)
    last_tuple_ins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_tuple_upd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_tuple_del: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stats_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observed_state_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_db_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_s3_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    rule: Mapped[BackupEventRule] = relationship(back_populates="state")
