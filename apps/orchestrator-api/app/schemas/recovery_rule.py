from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecoveryRuleDbSourceConfig(BaseModel):
    backupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    sourceEndpoint: str = Field(min_length=1, max_length=255)
    sourceBucketName: str = Field(min_length=1, max_length=120)
    sourceAccessKeyId: str = Field(min_length=1, max_length=255)
    sourceSecretAccessKey: str = Field(min_length=1)
    destinationHost: str = Field(min_length=1, max_length=255)
    destinationName: str = Field(min_length=1, max_length=120)
    destinationUsername: str = Field(min_length=1, max_length=120)
    destinationPassword: str = Field(min_length=1)


class RecoveryRuleDbUpdateConfig(BaseModel):
    backupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    sourceEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    sourceBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    sourceAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    sourceSecretAccessKey: str | None = None
    destinationHost: str | None = Field(default=None, min_length=1, max_length=255)
    destinationName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationUsername: str | None = Field(default=None, min_length=1, max_length=120)
    destinationPassword: str | None = None


class RecoveryRuleS3SourceConfig(BaseModel):
    backupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    sourceEndpoint: str = Field(min_length=1, max_length=255)
    sourceBucketName: str = Field(min_length=1, max_length=120)
    sourceAccessKeyId: str = Field(min_length=1, max_length=255)
    sourceSecretAccessKey: str = Field(min_length=1)
    destinationEndpoint: str = Field(min_length=1, max_length=255)
    destinationBucketName: str = Field(min_length=1, max_length=120)
    destinationSubfolderName: str | None = Field(default=None, max_length=255)
    destinationAccessKeyId: str = Field(min_length=1, max_length=255)
    destinationSecretAccessKey: str = Field(min_length=1)


class RecoveryRuleS3UpdateConfig(BaseModel):
    backupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    sourceEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    sourceBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    sourceAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    sourceSecretAccessKey: str | None = None
    destinationEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    destinationBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationSubfolderName: str | None = Field(default=None, max_length=255)
    destinationAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    destinationSecretAccessKey: str | None = None


class RecoveryEventRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    namespace: str = Field(min_length=1, max_length=120)
    enabled: bool = False
    db: RecoveryRuleDbSourceConfig
    s3: RecoveryRuleS3SourceConfig


class RecoveryEventRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    db: RecoveryRuleDbUpdateConfig | None = None
    s3: RecoveryRuleS3UpdateConfig | None = None


class RecoveryEventRuleDbDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    backupsFilenamePrefix: str
    sourceEndpoint: str
    sourceBucketName: str
    sourceAccessKeyId: str
    destinationHost: str
    destinationName: str
    destinationUsername: str
    hasSourceSecret: bool
    hasDestinationPassword: bool


class RecoveryEventRuleS3Detail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    backupsFilenamePrefix: str
    sourceEndpoint: str
    sourceBucketName: str
    sourceAccessKeyId: str
    destinationEndpoint: str
    destinationBucketName: str
    destinationSubfolderName: str
    destinationAccessKeyId: str
    hasSourceSecret: bool
    hasDestinationSecret: bool


class RecoveryEventRuleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    namespace: str
    enabled: bool
    dbName: str
    s3Name: str
    eventWatcherStatus: str
    lastPolledAt: datetime | None
    lastDbEmptyAt: datetime | None
    lastS3EmptyAt: datetime | None
    lastDbTriggeredAt: datetime | None
    lastS3TriggeredAt: datetime | None
    lastErrorAt: datetime | None
    lastErrorMessage: str | None
    updatedAt: datetime


class RecoveryEventRuleDetail(RecoveryEventRuleSummary):
    db: RecoveryEventRuleDbDetail
    s3: RecoveryEventRuleS3Detail