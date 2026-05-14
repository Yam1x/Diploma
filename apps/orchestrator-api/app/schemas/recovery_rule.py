from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecoveryEventRuleDbConfigInput(BaseModel):
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


class RecoveryEventRuleS3ConfigInput(BaseModel):
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


class RecoveryEventRuleDbConfigUpdate(BaseModel):
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


class RecoveryEventRuleS3ConfigUpdate(BaseModel):
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
    dbConfig: RecoveryEventRuleDbConfigInput
    s3Config: RecoveryEventRuleS3ConfigInput


class RecoveryEventRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    dbConfig: RecoveryEventRuleDbConfigUpdate | None = None
    s3Config: RecoveryEventRuleS3ConfigUpdate | None = None


class RecoveryEventRuleComponentDetail(BaseModel):
    name: str


class RecoveryEventRuleDbConfigDetail(RecoveryEventRuleComponentDetail):
    dbBackupsFilenamePrefix: str
    sourceAwsEndpoint: str
    sourceAwsBucketName: str
    sourceAwsAccessKeyId: str
    targetDatabaseHost: str
    targetDatabaseName: str
    targetDatabaseUsername: str
    hasSourceAwsSecretAccessKey: bool
    hasTargetDatabasePassword: bool


class RecoveryEventRuleS3ConfigDetail(RecoveryEventRuleComponentDetail):
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


class RecoveryEventRuleWatcher(BaseModel):
    status: str
    lastPolledAt: datetime | None
    lastDbEmptyAt: datetime | None
    lastS3EmptyAt: datetime | None
    lastDbTriggeredAt: datetime | None
    lastS3TriggeredAt: datetime | None
    lastErrorAt: datetime | None
    lastErrorMessage: str | None


class RecoveryEventRuleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    namespace: str
    enabled: bool
    dbConfig: RecoveryEventRuleComponentDetail
    s3Config: RecoveryEventRuleComponentDetail
    watcher: RecoveryEventRuleWatcher
    updatedAt: datetime


class RecoveryEventRuleDetail(RecoveryEventRuleSummary):
    dbConfig: RecoveryEventRuleDbConfigDetail
    s3Config: RecoveryEventRuleS3ConfigDetail
