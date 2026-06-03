from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


class TaskRequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    namespace: str = Field(min_length=1, max_length=120)
    enabled: bool = False
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual", "scheduled", "event_based"] = "scheduled"


class DbBackupTaskConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dbBackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    databaseHost: str = Field(min_length=1, max_length=255)
    databaseName: str = Field(min_length=1, max_length=120)
    databaseUsername: str = Field(min_length=1, max_length=120)
    databasePassword: str = Field(min_length=1)
    destinationAwsEndpoint: str = Field(min_length=1, max_length=255)
    destinationAwsBucketName: str = Field(min_length=1, max_length=120)
    destinationAwsAccessKeyId: str = Field(min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str = Field(min_length=1)


class S3BackupTaskConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class EnvBackupTaskConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    envBackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    destinationAwsEndpoint: str = Field(min_length=1, max_length=255)
    destinationAwsBucketName: str = Field(min_length=1, max_length=120)
    destinationAwsAccessKeyId: str = Field(min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str = Field(min_length=1)


class DbRestoreTaskConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dbBackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    sourceAwsEndpoint: str = Field(min_length=1, max_length=255)
    sourceAwsBucketName: str = Field(min_length=1, max_length=120)
    sourceAwsAccessKeyId: str = Field(min_length=1, max_length=255)
    sourceAwsSecretAccessKey: str = Field(min_length=1)
    targetDatabaseHost: str = Field(min_length=1, max_length=255)
    targetDatabaseName: str = Field(min_length=1, max_length=120)
    targetDatabaseUsername: str = Field(min_length=1, max_length=120)
    targetDatabasePassword: str = Field(min_length=1)


class S3RestoreTaskConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class EnvRestoreTaskConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    envBackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    sourceAwsEndpoint: str = Field(min_length=1, max_length=255)
    sourceAwsBucketName: str = Field(min_length=1, max_length=120)
    sourceAwsAccessKeyId: str = Field(min_length=1, max_length=255)
    sourceAwsSecretAccessKey: str = Field(min_length=1)


class EnvSyncTaskConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    envRepository: str = Field(min_length=1, max_length=255)
    pathToHelmfile: str = Field(min_length=1, max_length=255)


class DbTaskCreate(TaskRequestBase):
    serviceType: Literal["db_backupper"]
    triggerMode: Literal["scheduled"] = "scheduled"
    config: DbBackupTaskConfigInput


class S3TaskCreate(TaskRequestBase):
    serviceType: Literal["s3_backupper"]
    triggerMode: Literal["scheduled"] = "scheduled"
    config: S3BackupTaskConfigInput


class EnvBackupperTaskCreate(TaskRequestBase):
    serviceType: Literal["env_backupper"]
    triggerMode: Literal["scheduled"] = "scheduled"
    config: EnvBackupTaskConfigInput


class DbRestorerTaskCreate(TaskRequestBase):
    serviceType: Literal["db_restorer"]
    triggerMode: Literal["manual"] = "manual"
    config: DbRestoreTaskConfigInput


class S3RestorerTaskCreate(TaskRequestBase):
    serviceType: Literal["s3_restorer"]
    triggerMode: Literal["manual"] = "manual"
    config: S3RestoreTaskConfigInput


class EnvRestorerTaskCreate(TaskRequestBase):
    serviceType: Literal["env_restorer"]
    triggerMode: Literal["manual"] = "manual"
    config: EnvRestoreTaskConfigInput


class EnvSynchronizerTaskCreate(TaskRequestBase):
    serviceType: Literal["env_synchronizer"]
    triggerMode: Literal["scheduled"] = "scheduled"
    config: EnvSyncTaskConfigInput


TaskCreate: TypeAlias = Annotated[
    DbTaskCreate
    | S3TaskCreate
    | EnvBackupperTaskCreate
    | DbRestorerTaskCreate
    | S3RestorerTaskCreate
    | EnvRestorerTaskCreate
    | EnvSynchronizerTaskCreate,
    Field(discriminator="serviceType"),
]


class DbBackupTaskConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dbBackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    databaseHost: str | None = Field(default=None, min_length=1, max_length=255)
    databaseName: str | None = Field(default=None, min_length=1, max_length=120)
    databaseUsername: str | None = Field(default=None, min_length=1, max_length=120)
    databasePassword: str | None = None
    destinationAwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str | None = None


class S3BackupTaskConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class EnvBackupTaskConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    envBackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str | None = None


class DbRestoreTaskConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dbBackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    sourceAwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    sourceAwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    sourceAwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    sourceAwsSecretAccessKey: str | None = None
    targetDatabaseHost: str | None = Field(default=None, min_length=1, max_length=255)
    targetDatabaseName: str | None = Field(default=None, min_length=1, max_length=120)
    targetDatabaseUsername: str | None = Field(default=None, min_length=1, max_length=120)
    targetDatabasePassword: str | None = None


class S3RestoreTaskConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class EnvRestoreTaskConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    envBackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    sourceAwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    sourceAwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    sourceAwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    sourceAwsSecretAccessKey: str | None = None


class EnvSyncTaskConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    envRepository: str | None = Field(default=None, min_length=1, max_length=255)
    pathToHelmfile: str | None = Field(default=None, min_length=1, max_length=255)


class DbTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["db_backupper"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["scheduled"] | None = None
    config: DbBackupTaskConfigUpdate | None = None


class S3TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["s3_backupper"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["scheduled"] | None = None
    config: S3BackupTaskConfigUpdate | None = None


class EnvBackupperTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["env_backupper"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["scheduled"] | None = None
    config: EnvBackupTaskConfigUpdate | None = None


class DbRestorerTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["db_restorer"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual"] | None = None
    config: DbRestoreTaskConfigUpdate | None = None


class S3RestorerTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["s3_restorer"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual"] | None = None
    config: S3RestoreTaskConfigUpdate | None = None


class EnvRestorerTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["env_restorer"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual"] | None = None
    config: EnvRestoreTaskConfigUpdate | None = None


class EnvSynchronizerTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["env_synchronizer"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["scheduled"] | None = None
    config: EnvSyncTaskConfigUpdate | None = None


TaskUpdate: TypeAlias = Annotated[
    DbTaskUpdate
    | S3TaskUpdate
    | EnvBackupperTaskUpdate
    | DbRestorerTaskUpdate
    | S3RestorerTaskUpdate
    | EnvRestorerTaskUpdate
    | EnvSynchronizerTaskUpdate,
    Field(discriminator="serviceType"),
]


class TaskSummaryBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    namespace: str
    enabled: bool
    serviceType: Literal["db_backupper", "s3_backupper", "env_backupper", "db_restorer", "s3_restorer", "env_restorer", "env_synchronizer"]
    schedule: str | None
    triggerMode: Literal["manual", "scheduled"]
    deployed: bool
    releaseName: str
    lastApplyStatus: str | None
    lastApplyMessage: str | None
    lastAppliedAt: datetime | None
    updatedAt: datetime


class DbBackupTaskConfigDetail(BaseModel):
    dbBackupsFilenamePrefix: str
    databaseHost: str
    databaseName: str
    databaseUsername: str
    destinationAwsEndpoint: str
    destinationAwsBucketName: str
    destinationAwsAccessKeyId: str
    hasDatabasePassword: bool
    hasDestinationAwsSecretAccessKey: bool


class S3BackupTaskConfigDetail(BaseModel):
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


class EnvBackupTaskConfigDetail(BaseModel):
    envBackupsFilenamePrefix: str
    destinationAwsEndpoint: str
    destinationAwsBucketName: str
    destinationAwsAccessKeyId: str
    hasDestinationAwsSecretAccessKey: bool


class DbRestoreTaskConfigDetail(BaseModel):
    dbBackupsFilenamePrefix: str
    sourceAwsEndpoint: str
    sourceAwsBucketName: str
    sourceAwsAccessKeyId: str
    targetDatabaseHost: str
    targetDatabaseName: str
    targetDatabaseUsername: str
    hasSourceAwsSecretAccessKey: bool
    hasTargetDatabasePassword: bool


class S3RestoreTaskConfigDetail(BaseModel):
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


class EnvRestoreTaskConfigDetail(BaseModel):
    envBackupsFilenamePrefix: str
    sourceAwsEndpoint: str
    sourceAwsBucketName: str
    sourceAwsAccessKeyId: str
    hasSourceAwsSecretAccessKey: bool


class EnvSyncTaskConfigDetail(BaseModel):
    envRepository: str
    pathToHelmfile: str


class DbTaskDetail(TaskSummaryBase):
    serviceType: Literal["db_backupper"]
    config: DbBackupTaskConfigDetail


class S3TaskDetail(TaskSummaryBase):
    serviceType: Literal["s3_backupper"]
    config: S3BackupTaskConfigDetail


class EnvBackupperTaskDetail(TaskSummaryBase):
    serviceType: Literal["env_backupper"]
    config: EnvBackupTaskConfigDetail


class DbRestorerTaskDetail(TaskSummaryBase):
    serviceType: Literal["db_restorer"]
    config: DbRestoreTaskConfigDetail


class S3RestorerTaskDetail(TaskSummaryBase):
    serviceType: Literal["s3_restorer"]
    config: S3RestoreTaskConfigDetail


class EnvRestorerTaskDetail(TaskSummaryBase):
    serviceType: Literal["env_restorer"]
    config: EnvRestoreTaskConfigDetail


class EnvSynchronizerTaskDetail(TaskSummaryBase):
    serviceType: Literal["env_synchronizer"]
    config: EnvSyncTaskConfigDetail


TaskDetail: TypeAlias = Annotated[
    DbTaskDetail
    | S3TaskDetail
    | EnvBackupperTaskDetail
    | DbRestorerTaskDetail
    | S3RestorerTaskDetail
    | EnvRestorerTaskDetail
    | EnvSynchronizerTaskDetail,
    Field(discriminator="serviceType"),
]


TaskSummary: TypeAlias = TaskSummaryBase


class HealthResponse(BaseModel):
    status: str


class NamespaceListResponse(BaseModel):
    namespaces: list[str]


class NamespaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class NamespaceResponse(BaseModel):
    name: str


class ServiceDiscoveryEndpoint(BaseModel):
    label: str
    value: str


class ServiceDiscoveryServicePort(BaseModel):
    name: str | None
    port: int


class ServiceDiscoveryService(BaseModel):
    name: str
    host: str
    ports: list[ServiceDiscoveryServicePort]
    endpoints: list[ServiceDiscoveryEndpoint]


class ServiceDiscoveryResponse(BaseModel):
    services: list[ServiceDiscoveryService]
