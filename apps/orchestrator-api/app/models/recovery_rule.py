from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RecoveryEventRule(Base):
    __tablename__ = "recovery_event_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    namespace: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    db_config: Mapped["RecoveryEventRuleDbConfig | None"] = relationship(back_populates="rule", uselist=False, cascade="all, delete-orphan")
    s3_config: Mapped["RecoveryEventRuleS3Config | None"] = relationship(back_populates="rule", uselist=False, cascade="all, delete-orphan")


class RecoveryEventRuleDbConfig(Base):
    __tablename__ = "recovery_event_rule_db_configs"

    rule_id: Mapped[int] = mapped_column(ForeignKey("recovery_event_rules.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    db_backups_filename_prefix: Mapped[str] = mapped_column(String(120), nullable=False)
    source_aws_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    source_aws_bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_aws_access_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_aws_secret_access_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_database_host: Mapped[str] = mapped_column(String(255), nullable=False)
    target_database_name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_database_username: Mapped[str] = mapped_column(String(120), nullable=False)
    target_database_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    rule: Mapped[RecoveryEventRule] = relationship(back_populates="db_config")


class RecoveryEventRuleS3Config(Base):
    __tablename__ = "recovery_event_rule_s3_configs"

    rule_id: Mapped[int] = mapped_column(ForeignKey("recovery_event_rules.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
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

    rule: Mapped[RecoveryEventRule] = relationship(back_populates="s3_config")
