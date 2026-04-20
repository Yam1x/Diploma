from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BackupEventRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    enabled: bool = False
    dbTaskId: int = Field(ge=1)
    s3TaskId: int = Field(ge=1)


class BackupEventRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    dbTaskId: int | None = Field(default=None, ge=1)
    s3TaskId: int | None = Field(default=None, ge=1)


class BackupEventRuleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    enabled: bool
    dbTaskId: int
    dbTaskName: str
    s3TaskId: int
    s3TaskName: str
    eventWatcherStatus: str
    lastTriggeredAt: datetime | None
    updatedAt: datetime


class BackupEventRuleDetail(BackupEventRuleSummary):
    lastPolledAt: datetime | None
    lastDbChangeAt: datetime | None
    lastS3ChangeAt: datetime | None
    lastErrorAt: datetime | None
    lastErrorMessage: str | None
