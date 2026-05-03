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
    triggerMode: Literal["scheduled", "event_based"] = "scheduled"


class DbTaskCreate(TaskRequestBase):
    serviceType: Literal["db_backupper"]
    dbBackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    databaseHost: str = Field(min_length=1, max_length=255)
    databaseName: str = Field(min_length=1, max_length=120)
    databaseUsername: str = Field(min_length=1, max_length=120)
    databasePassword: str = Field(min_length=1)
    destinationAwsEndpoint: str = Field(min_length=1, max_length=255)
    destinationAwsBucketName: str = Field(min_length=1, max_length=120)
    destinationAwsAccessKeyId: str = Field(min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str = Field(min_length=1)


class S3TaskCreate(TaskRequestBase):
    serviceType: Literal["s3_backupper"]
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


class EnvBackupperTaskCreate(TaskRequestBase):
    serviceType: Literal["env_backupper"]
    envBackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    destinationAwsEndpoint: str = Field(min_length=1, max_length=255)
    destinationAwsBucketName: str = Field(min_length=1, max_length=120)
    destinationAwsAccessKeyId: str = Field(min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str = Field(min_length=1)


class EnvRestorerTaskCreate(TaskRequestBase):
    serviceType: Literal["env_restorer"]
    envBackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    destinationAwsEndpoint: str = Field(min_length=1, max_length=255)
    destinationAwsBucketName: str = Field(min_length=1, max_length=120)
    destinationAwsAccessKeyId: str = Field(min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str = Field(min_length=1)


class EnvSynchronizerTaskCreate(TaskRequestBase):
    serviceType: Literal["env_synchronizer"]
    envRepository: str = Field(min_length=1, max_length=255)
    pathToHelmfile: str = Field(min_length=1, max_length=255)


TaskCreate: TypeAlias = Annotated[
    DbTaskCreate | S3TaskCreate | EnvBackupperTaskCreate | EnvRestorerTaskCreate | EnvSynchronizerTaskCreate,
    Field(discriminator="serviceType"),
]


class DbTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["db_backupper"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["scheduled", "event_based"] | None = None
    dbBackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    databaseHost: str | None = Field(default=None, min_length=1, max_length=255)
    databaseName: str | None = Field(default=None, min_length=1, max_length=120)
    databaseUsername: str | None = Field(default=None, min_length=1, max_length=120)
    databasePassword: str | None = None
    destinationAwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str | None = None


class S3TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["s3_backupper"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["scheduled", "event_based"] | None = None
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


class EnvBackupperTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["env_backupper"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["scheduled", "event_based"] | None = None
    envBackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str | None = None


class EnvRestorerTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["env_restorer"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["scheduled", "event_based"] | None = None
    envBackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str | None = None


class EnvSynchronizerTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["env_synchronizer"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["scheduled", "event_based"] | None = None
    envRepository: str | None = Field(default=None, min_length=1, max_length=255)
    pathToHelmfile: str | None = Field(default=None, min_length=1, max_length=255)


TaskUpdate: TypeAlias = Annotated[
    DbTaskUpdate | S3TaskUpdate | EnvBackupperTaskUpdate | EnvRestorerTaskUpdate | EnvSynchronizerTaskUpdate,
    Field(discriminator="serviceType"),
]


class TaskSummaryBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    namespace: str
    enabled: bool
    serviceType: Literal["db_backupper", "s3_backupper", "env_backupper", "env_restorer", "env_synchronizer"]
    schedule: str | None
    triggerMode: Literal["scheduled", "event_based"]
    deployed: bool
    releaseName: str
    lastApplyStatus: str | None
    lastApplyMessage: str | None
    lastAppliedAt: datetime | None
    updatedAt: datetime


class DbTaskSummary(TaskSummaryBase):
    serviceType: Literal["db_backupper"]


class S3TaskSummary(TaskSummaryBase):
    serviceType: Literal["s3_backupper"]


class EnvBackupperTaskSummary(TaskSummaryBase):
    serviceType: Literal["env_backupper"]


class EnvRestorerTaskSummary(TaskSummaryBase):
    serviceType: Literal["env_restorer"]


class EnvSynchronizerTaskSummary(TaskSummaryBase):
    serviceType: Literal["env_synchronizer"]


TaskSummary: TypeAlias = Annotated[
    DbTaskSummary | S3TaskSummary | EnvBackupperTaskSummary | EnvRestorerTaskSummary | EnvSynchronizerTaskSummary,
    Field(discriminator="serviceType"),
]


class DbTaskDetail(DbTaskSummary):
    dbBackupsFilenamePrefix: str
    databaseHost: str
    databaseName: str
    databaseUsername: str
    destinationAwsEndpoint: str
    destinationAwsBucketName: str
    destinationAwsAccessKeyId: str
    hasDatabasePassword: bool
    hasDestinationAwsSecretAccessKey: bool
    eventWatcherStatus: str
    lastEventDetectedAt: datetime | None
    lastEventTriggeredAt: datetime | None
    lastEventMessage: str | None


class S3TaskDetail(S3TaskSummary):
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
    eventWatcherStatus: str
    lastEventDetectedAt: datetime | None
    lastEventTriggeredAt: datetime | None
    lastEventMessage: str | None


class EnvBackupperTaskDetail(EnvBackupperTaskSummary):
    envBackupsFilenamePrefix: str
    destinationAwsEndpoint: str
    destinationAwsBucketName: str
    destinationAwsAccessKeyId: str
    hasDestinationAwsSecretAccessKey: bool


class EnvRestorerTaskDetail(EnvRestorerTaskSummary):
    envBackupsFilenamePrefix: str
    destinationAwsEndpoint: str
    destinationAwsBucketName: str
    destinationAwsAccessKeyId: str
    hasDestinationAwsSecretAccessKey: bool


class EnvSynchronizerTaskDetail(EnvSynchronizerTaskSummary):
    envRepository: str
    pathToHelmfile: str


TaskDetail: TypeAlias = Annotated[
    DbTaskDetail | S3TaskDetail | EnvBackupperTaskDetail | EnvRestorerTaskDetail | EnvSynchronizerTaskDetail,
    Field(discriminator="serviceType"),
]


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
