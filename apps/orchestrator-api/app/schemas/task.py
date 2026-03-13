from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    namespace: str = Field(min_length=1, max_length=120)
    enabled: bool = False
    serviceType: Literal["db_backupper"] = "db_backupper"
    schedule: str = Field(min_length=1, max_length=120)
    dbBackupsFilenamePrefix: str = Field(min_length=1, max_length=120)
    databaseHost: str = Field(min_length=1, max_length=255)
    databaseName: str = Field(min_length=1, max_length=120)
    databaseUsername: str = Field(min_length=1, max_length=120)
    destinationAwsEndpoint: str = Field(min_length=1, max_length=255)
    destinationAwsBucketName: str = Field(min_length=1, max_length=120)
    destinationAwsAccessKeyId: str = Field(min_length=1, max_length=255)


class TaskCreate(TaskBase):
    databasePassword: str = Field(min_length=1)
    destinationAwsSecretAccessKey: str = Field(min_length=1)


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    namespace: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    schedule: str | None = Field(default=None, min_length=1, max_length=120)
    dbBackupsFilenamePrefix: str | None = Field(default=None, min_length=1, max_length=120)
    databaseHost: str | None = Field(default=None, min_length=1, max_length=255)
    databaseName: str | None = Field(default=None, min_length=1, max_length=120)
    databaseUsername: str | None = Field(default=None, min_length=1, max_length=120)
    databasePassword: str | None = None
    destinationAwsEndpoint: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsBucketName: str | None = Field(default=None, min_length=1, max_length=120)
    destinationAwsAccessKeyId: str | None = Field(default=None, min_length=1, max_length=255)
    destinationAwsSecretAccessKey: str | None = None


class TaskSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    namespace: str
    enabled: bool
    serviceType: str
    schedule: str
    deployed: bool
    releaseName: str
    lastApplyStatus: str | None
    lastApplyMessage: str | None
    lastAppliedAt: datetime | None
    updatedAt: datetime


class TaskDetail(TaskSummary):
    dbBackupsFilenamePrefix: str
    databaseHost: str
    databaseName: str
    databaseUsername: str
    destinationAwsEndpoint: str
    destinationAwsBucketName: str
    destinationAwsAccessKeyId: str
    hasDatabasePassword: bool
    hasDestinationAwsSecretAccessKey: bool


class HealthResponse(BaseModel):
    status: str


class NamespaceListResponse(BaseModel):
    namespaces: list[str]


class NamespaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class NamespaceResponse(BaseModel):
    name: str
