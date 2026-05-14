from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


class DatabaseSourceConfig(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1)


class S3SourceConfig(BaseModel):
    endpoint: str = Field(min_length=1, max_length=255)
    bucketName: str = Field(min_length=1, max_length=120)
    accessKeyId: str = Field(min_length=1, max_length=255)
    secretAccessKey: str = Field(min_length=1)
    subfolderName: str | None = Field(default=None, max_length=255)


class S3DestinationConfig(BaseModel):
    endpoint: str = Field(min_length=1, max_length=255)
    bucketName: str = Field(min_length=1, max_length=120)
    accessKeyId: str = Field(min_length=1, max_length=255)
    secretAccessKey: str = Field(min_length=1)


class DatabaseDestinationConfig(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1)


class TaskRequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    namespace: str = Field(min_length=1, max_length=120)
    enabled: bool = False
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual", "scheduled", "event_based"] = "scheduled"


class DbTaskCreate(TaskRequestBase):
    serviceType: Literal["db_backupper"]
    filenamePrefix: str = Field(min_length=1, max_length=120)
    source: DatabaseSourceConfig
    destination: S3DestinationConfig


class S3TaskCreate(TaskRequestBase):
    serviceType: Literal["s3_backupper"]
    filenamePrefix: str = Field(min_length=1, max_length=120)
    source: S3SourceConfig
    destination: S3DestinationConfig


class EnvBackupperTaskCreate(TaskRequestBase):
    serviceType: Literal["env_backupper"]
    filenamePrefix: str = Field(min_length=1, max_length=120)
    destination: S3DestinationConfig


class DbRestorerTaskCreate(TaskRequestBase):
    serviceType: Literal["db_restorer"]
    filenamePrefix: str = Field(min_length=1, max_length=120)
    source: S3SourceConfig
    destination: DatabaseDestinationConfig


class S3RestorerTaskCreate(TaskRequestBase):
    serviceType: Literal["s3_restorer"]
    filenamePrefix: str = Field(min_length=1, max_length=120)
    source: S3SourceConfig
    destination: S3SourceConfig


class EnvRestorerTaskCreate(TaskRequestBase):
    serviceType: Literal["env_restorer"]
    filenamePrefix: str = Field(min_length=1, max_length=120)
    source: S3DestinationConfig


class EnvSynchronizerTaskCreate(TaskRequestBase):
    serviceType: Literal["env_synchronizer"]
    repository: str = Field(min_length=1, max_length=255)
    pathToHelmfile: str = Field(min_length=1, max_length=255)


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


class DbTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["db_backupper"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual", "scheduled", "event_based"] | None = None
    filenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    source: DatabaseSourceConfig | None = None
    destination: S3DestinationConfig | None = None


class S3TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["s3_backupper"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual", "scheduled", "event_based"] | None = None
    filenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    source: S3SourceConfig | None = None
    destination: S3DestinationConfig | None = None


class EnvBackupperTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["env_backupper"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual", "scheduled", "event_based"] | None = None
    filenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    destination: S3DestinationConfig | None = None


class DbRestorerTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["db_restorer"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual", "scheduled", "event_based"] | None = None
    filenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    source: S3SourceConfig | None = None
    destination: DatabaseDestinationConfig | None = None


class S3RestorerTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["s3_restorer"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual", "scheduled", "event_based"] | None = None
    filenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    source: S3SourceConfig | None = None
    destination: S3SourceConfig | None = None


class EnvRestorerTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["env_restorer"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual", "scheduled", "event_based"] | None = None
    filenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    source: S3DestinationConfig | None = None


class EnvSynchronizerTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceType: Literal["env_synchronizer"]
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    triggerMode: Literal["manual", "scheduled", "event_based"] | None = None
    repository: str | None = Field(default=None, min_length=1, max_length=255)
    pathToHelmfile: str | None = Field(default=None, min_length=1, max_length=255)


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
    triggerMode: Literal["manual", "scheduled", "event_based"]
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


class DbRestorerTaskSummary(TaskSummaryBase):
    serviceType: Literal["db_restorer"]


class S3RestorerTaskSummary(TaskSummaryBase):
    serviceType: Literal["s3_restorer"]


class EnvRestorerTaskSummary(TaskSummaryBase):
    serviceType: Literal["env_restorer"]


class EnvSynchronizerTaskSummary(TaskSummaryBase):
    serviceType: Literal["env_synchronizer"]


TaskSummary: TypeAlias = Annotated[
    DbTaskSummary
    | S3TaskSummary
    | EnvBackupperTaskSummary
    | DbRestorerTaskSummary
    | S3RestorerTaskSummary
    | EnvRestorerTaskSummary
    | EnvSynchronizerTaskSummary,
    Field(discriminator="serviceType"),
]


class DbTaskDetail(DbTaskSummary):
    filenamePrefix: str
    sourceHost: str
    sourceName: str
    sourceUsername: str
    destinationEndpoint: str
    destinationBucketName: str
    destinationAccessKeyId: str
    hasSourcePassword: bool
    hasDestinationSecret: bool
    eventWatcherStatus: str
    lastEventDetectedAt: datetime | None
    lastEventTriggeredAt: datetime | None
    lastEventMessage: str | None


class S3TaskDetail(S3TaskSummary):
    filenamePrefix: str
    sourceEndpoint: str
    sourceAccessKeyId: str
    sourceBucketName: str
    sourceSubfolderName: str
    destinationEndpoint: str
    destinationAccessKeyId: str
    destinationBucketName: str
    hasSourceSecret: bool
    hasDestinationSecret: bool
    eventWatcherStatus: str
    lastEventDetectedAt: datetime | None
    lastEventTriggeredAt: datetime | None
    lastEventMessage: str | None


class EnvBackupperTaskDetail(EnvBackupperTaskSummary):
    filenamePrefix: str
    destinationEndpoint: str
    destinationBucketName: str
    destinationAccessKeyId: str
    hasDestinationSecret: bool


class DbRestorerTaskDetail(DbRestorerTaskSummary):
    filenamePrefix: str
    sourceEndpoint: str
    sourceBucketName: str
    sourceAccessKeyId: str
    destinationHost: str
    destinationName: str
    destinationUsername: str
    hasSourceSecret: bool
    hasDestinationPassword: bool


class S3RestorerTaskDetail(S3RestorerTaskSummary):
    filenamePrefix: str
    sourceEndpoint: str
    sourceBucketName: str
    sourceAccessKeyId: str
    destinationEndpoint: str
    destinationBucketName: str
    destinationSubfolderName: str
    destinationAccessKeyId: str
    hasSourceSecret: bool
    hasDestinationSecret: bool


class EnvRestorerTaskDetail(EnvRestorerTaskSummary):
    filenamePrefix: str
    sourceEndpoint: str
    sourceBucketName: str
    sourceAccessKeyId: str
    hasSourceSecret: bool


class EnvSynchronizerTaskDetail(EnvSynchronizerTaskSummary):
    repository: str
    pathToHelmfile: str


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