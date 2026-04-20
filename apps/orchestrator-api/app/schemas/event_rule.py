from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BackupEventRuleDbConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    dbBackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    databaseHost: str = Field(min_length=1, max_length=255)
    databaseName: str = Field(min_length=1, max_length=120)
    databaseUsername: str = Field(min_length=1, max_length=120)
    databasePassword: str = Field(min_length=1)
    destinationAwsEndpoint: str = Field(min_length=1, max_length=255)
    destinationAwsBucketName: str = Field(min_length=1, max_length=120)
    destinationAwsAccessKeyId: str = Field(min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str = Field(min_length=1)


class BackupEventRuleDbUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    dbBackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    databaseHost: str | None = Field(default=None, min_length=1, max_length=255)
    databaseName: str | None = Field(default=None, min_length=1, max_length=120)
    databaseUsername: str | None = Field(default=None, min_length=1, max_length=120)
    databasePassword: str | None = None
    destinationAwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str | None = None


class BackupEventRuleS3Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    s3BackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    sourceS3AwsEndpoint: str = Field(min_length=1, max_length=255)
    sourceS3AwsAccessKeyId: str = Field(min_length=1, max_length=255)
    sourceS3AwsBucketName: str = Field(min_length=1, max_length=120)
    sourceS3AwsBucketSubfolderName: str | None = Field(default=None, max_length=255)
    sourceS3AwsSecretAccessKey: str = Field(min_length=1)
    destinationS3AwsEndpoint: str = Field(min_length=1, max_length=255)
    destinationS3AwsAccessKeyId: str = Field(min_length=1, max_length=255)
    destinationS3AwsBucketName: str = Field(min_length=1, max_length=120)
    destinationS3AwsSecretAccessKey: str = Field(min_length=1)


class BackupEventRuleS3Update(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    s3BackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    sourceS3AwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    sourceS3AwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    sourceS3AwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    sourceS3AwsBucketSubfolderName: str | None = Field(default=None, max_length=255)
    sourceS3AwsSecretAccessKey: str | None = None
    destinationS3AwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    destinationS3AwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    destinationS3AwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationS3AwsSecretAccessKey: str | None = None


class BackupEventRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    namespace: str = Field(min_length=1, max_length=120)
    enabled: bool = False
    db: BackupEventRuleDbConfig
    s3: BackupEventRuleS3Config


class BackupEventRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    db: BackupEventRuleDbUpdate | None = None
    s3: BackupEventRuleS3Update | None = None


class BackupEventRuleDbDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    dbBackupsFilenamePrefix: str
    databaseHost: str
    databaseName: str
    databaseUsername: str
    destinationAwsEndpoint: str
    destinationAwsBucketName: str
    destinationAwsAccessKeyId: str
    hasDatabasePassword: bool
    hasDestinationAwsSecretAccessKey: bool


class BackupEventRuleS3Detail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    s3BackupsFilenamePrefix: str
    sourceS3AwsEndpoint: str
    sourceS3AwsAccessKeyId: str
    sourceS3AwsBucketName: str
    sourceS3AwsBucketSubfolderName: str
    destinationS3AwsEndpoint: str
    destinationS3AwsAccessKeyId: str
    destinationS3AwsBucketName: str
    hasSourceS3AwsSecretAccessKey: bool
    hasDestinationS3AwsSecretAccessKey: bool


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
