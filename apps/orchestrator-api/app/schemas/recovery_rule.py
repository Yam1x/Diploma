from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecoveryEventRuleDbConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    dbBackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    sourceAwsEndpoint: str = Field(min_length=1, max_length=255)
    sourceAwsBucketName: str = Field(min_length=1, max_length=120)
    sourceAwsAccessKeyId: str = Field(min_length=1, max_length=255)
    sourceAwsSecretAccessKey: str = Field(min_length=1)
    targetDatabaseHost: str = Field(min_length=1, max_length=255)
    targetDatabaseName: str = Field(min_length=1, max_length=120)
    targetDatabaseUsername: str = Field(min_length=1, max_length=120)
    targetDatabasePassword: str = Field(min_length=1)


class RecoveryEventRuleDbUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    dbBackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    sourceAwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    sourceAwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    sourceAwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    sourceAwsSecretAccessKey: str | None = None
    targetDatabaseHost: str | None = Field(default=None, min_length=1, max_length=255)
    targetDatabaseName: str | None = Field(default=None, min_length=1, max_length=120)
    targetDatabaseUsername: str | None = Field(default=None, min_length=1, max_length=120)
    targetDatabasePassword: str | None = None


class RecoveryEventRuleS3Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    s3BackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    sourceS3AwsEndpoint: str = Field(min_length=1, max_length=255)
    sourceS3AwsBucketName: str = Field(min_length=1, max_length=120)
    sourceS3AwsAccessKeyId: str = Field(min_length=1, max_length=255)
    sourceS3AwsSecretAccessKey: str = Field(min_length=1)
    targetS3AwsEndpoint: str = Field(min_length=1, max_length=255)
    targetS3AwsBucketName: str = Field(min_length=1, max_length=120)
    targetS3AwsBucketSubfolderName: str | None = Field(default=None, max_length=255)
    targetS3AwsAccessKeyId: str = Field(min_length=1, max_length=255)
    targetS3AwsSecretAccessKey: str = Field(min_length=1)


class RecoveryEventRuleS3Update(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    s3BackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    sourceS3AwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    sourceS3AwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    sourceS3AwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    sourceS3AwsSecretAccessKey: str | None = None
    targetS3AwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    targetS3AwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    targetS3AwsBucketSubfolderName: str | None = Field(default=None, max_length=255)
    targetS3AwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    targetS3AwsSecretAccessKey: str | None = None


class RecoveryEventRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    namespace: str = Field(min_length=1, max_length=120)
    enabled: bool = False
    db: RecoveryEventRuleDbConfig
    s3: RecoveryEventRuleS3Config


class RecoveryEventRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    db: RecoveryEventRuleDbUpdate | None = None
    s3: RecoveryEventRuleS3Update | None = None


class RecoveryEventRuleDbDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    dbBackupsFilenamePrefix: str
    sourceAwsEndpoint: str
    sourceAwsBucketName: str
    sourceAwsAccessKeyId: str
    targetDatabaseHost: str
    targetDatabaseName: str
    targetDatabaseUsername: str
    hasSourceAwsSecretAccessKey: bool
    hasTargetDatabasePassword: bool


class RecoveryEventRuleS3Detail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    s3BackupsFilenamePrefix: str
    sourceS3AwsEndpoint: str
    sourceS3AwsBucketName: str
    sourceS3AwsAccessKeyId: str
    targetS3AwsEndpoint: str
    targetS3AwsBucketName: str
    targetS3AwsBucketSubfolderName: str
    targetS3AwsAccessKeyId: str
    hasSourceS3AwsSecretAccessKey: bool
    hasTargetS3AwsSecretAccessKey: bool


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
