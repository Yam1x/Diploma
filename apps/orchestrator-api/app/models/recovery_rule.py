from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.task import Task


class RecoveryEventRule(Base):
    __tablename__ = "recovery_event_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    namespace: Mapped[str] = mapped_column(String(120), nullable=False)
    db_display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    s3_display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    db_task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True, index=True)
    s3_task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True, index=True)
    db_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    s3_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    db_task: Mapped[Task | None] = relationship(Task, foreign_keys=[db_task_id])
    s3_task: Mapped[Task | None] = relationship(Task, foreign_keys=[s3_task_id])
    db_secret: Mapped["RecoveryEventRuleSecret | None"] = relationship(
        "RecoveryEventRuleSecret",
        primaryjoin="RecoveryEventRule.id == foreign(RecoveryEventRuleSecret.rule_id)",
        foreign_keys="RecoveryEventRuleSecret.rule_id",
        uselist=False,
        cascade="all, delete-orphan",
        viewonly=True,
    )
    s3_secret: Mapped["RecoveryEventRuleS3Secret | None"] = relationship(
        "RecoveryEventRuleS3Secret",
        primaryjoin="RecoveryEventRule.id == foreign(RecoveryEventRuleS3Secret.rule_id)",
        foreign_keys="RecoveryEventRuleS3Secret.rule_id",
        uselist=False,
        cascade="all, delete-orphan",
        viewonly=True,
    )
    state: Mapped["RecoveryEventRuleState | None"] = relationship(
        back_populates="rule",
        uselist=False,
        cascade="all, delete-orphan",
    )


class RecoveryEventRuleSecret(Base):
    __tablename__ = "recovery_event_rule_secrets"

    rule_id: Mapped[int] = mapped_column(ForeignKey("recovery_event_rules.id"), primary_key=True)
    source_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)


class RecoveryEventRuleS3Secret(Base):
    __tablename__ = "recovery_event_rule_s3_secrets"

    rule_id: Mapped[int] = mapped_column(ForeignKey("recovery_event_rules.id"), primary_key=True)
    source_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)


class RecoveryEventRuleState(Base):
    __tablename__ = "recovery_event_rule_states"

    rule_id: Mapped[int] = mapped_column(ForeignKey("recovery_event_rules.id"), primary_key=True)
    last_db_is_empty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_s3_is_empty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_db_had_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_s3_had_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    db_restore_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    s3_restore_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_db_empty_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_s3_empty_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_db_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_s3_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    rule: Mapped[RecoveryEventRule] = relationship(back_populates="state")