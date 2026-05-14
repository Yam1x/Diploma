from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventRuleDbSourceConfig(BaseModel):
    backupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1)
    destinationEndpoint: str = Field(min_length=1, max_length=255)
    destinationBucketName: str = Field(min_length=1, max_length=120)
    destinationAccessKeyId: str = Field(min_length=1, max_length=255)
    destinationSecretAccessKey: str = Field(min_length=1)


class EventRuleDbUpdateConfig(BaseModel):
    backupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    username: str | None = Field(default=None, min_length=1, max_length=120)
    password: str | None = None
    destinationEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    destinationBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    destinationSecretAccessKey: str | None = None


class EventRuleS3SourceConfig(BaseModel):
    backupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    sourceEndpoint: str = Field(min_length=1, max_length=255)
    sourceBucketName: str = Field(min_length=1, max_length=120)
    sourceAccessKeyId: str = Field(min_length=1, max_length=255)
    sourceSecretAccessKey: str = Field(min_length=1)
    sourceSubfolderName: str | None = Field(default=None, max_length=255)
    destinationEndpoint: str = Field(min_length=1, max_length=255)
    destinationBucketName: str = Field(min_length=1, max_length=120)
    destinationAccessKeyId: str = Field(min_length=1, max_length=255)
    destinationSecretAccessKey: str = Field(min_length=1)


class EventRuleS3UpdateConfig(BaseModel):
    backupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    sourceEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    sourceBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    sourceAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    sourceSecretAccessKey: str | None = None
    sourceSubfolderName: str | None = Field(default=None, max_length=255)
    destinationEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    destinationBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    destinationSecretAccessKey: str | None = None


class BackupEventRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    namespace: str = Field(min_length=1, max_length=120)
    enabled: bool = False
    db: EventRuleDbSourceConfig
    s3: EventRuleS3SourceConfig


class BackupEventRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    db: EventRuleDbUpdateConfig | None = None
    s3: EventRuleS3UpdateConfig | None = None


class BackupEventRuleDbDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    backupsFilenamePrefix: str
    host: str
    databaseName: str
    username: str
    destinationEndpoint: str
    destinationBucketName: str
    destinationAccessKeyId: str
    hasPassword: bool
    hasDestinationSecret: bool


class BackupEventRuleS3Detail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    backupsFilenamePrefix: str
    sourceEndpoint: str
    sourceBucketName: str
    sourceAccessKeyId: str
    sourceSubfolderName: str
    destinationEndpoint: str
    destinationBucketName: str
    destinationAccessKeyId: str
    hasSourceSecret: bool
    hasDestinationSecret: bool


class BackupEventRuleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    namespace: str
    enabled: bool
    dbName: str
    s3Name: str
    eventWatcherStatus: str
    lastTriggeredAt: datetime | None
    updatedAt: datetime


class BackupEventRuleDetail(BackupEventRuleSummary):
    db: BackupEventRuleDbDetail
    s3: BackupEventRuleS3Detail
    lastPolledAt: datetime | None
    lastDbChangeAt: datetime | None
    lastS3ChangeAt: datetime | None
    lastErrorAt: datetime | None
    lastErrorMessage: str | None