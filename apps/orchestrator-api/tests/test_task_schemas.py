from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.task import TaskCreate, TaskUpdate


CREATE_ADAPTER = TypeAdapter(TaskCreate)
UPDATE_ADAPTER = TypeAdapter(TaskUpdate)


def test_db_task_create_schema_accepts_db_payload() -> None:
    payload = {
        "serviceType": "db_backupper",
        "name": "Primary DB",
        "namespace": "default",
        "enabled": True,
        "schedule": "0 * * * *",
        "triggerMode": "event_based",
        "dbBackupsFilenamePrefix": "primary",
        "databaseHost": "postgresql",
        "databaseName": "app",
        "databaseUsername": "postgres",
        "databasePassword": "secret",
        "destinationAwsEndpoint": "https://minio.local",
        "destinationAwsBucketName": "backups",
        "destinationAwsAccessKeyId": "minio",
        "destinationAwsSecretAccessKey": "minio-secret",
    }

    result = CREATE_ADAPTER.validate_python(payload)

    assert result.serviceType == "db_backupper"
    assert result.dbBackupsFilenamePrefix == "primary"
    assert result.triggerMode == "event_based"


def test_s3_task_update_schema_accepts_s3_payload() -> None:
    payload = {
        "serviceType": "s3_backupper",
        "schedule": "15 * * * *",
        "triggerMode": "scheduled",
        "sourceS3AwsBucketSubfolderName": "incoming",
        "destinationS3AwsBucketName": "archive",
    }

    result = UPDATE_ADAPTER.validate_python(payload)

    assert result.serviceType == "s3_backupper"
    assert result.destinationS3AwsBucketName == "archive"


def test_create_schema_rejects_fields_for_wrong_service() -> None:
    payload = {
        "serviceType": "s3_backupper",
        "name": "Broken",
        "namespace": "default",
        "enabled": False,
        "schedule": "0 0 * * *",
        "dbBackupsFilenamePrefix": "wrong",
        "databaseHost": "postgresql",
        "databaseName": "app",
        "databaseUsername": "postgres",
        "databasePassword": "secret",
        "destinationAwsEndpoint": "https://minio.local",
        "destinationAwsBucketName": "backups",
        "destinationAwsAccessKeyId": "minio",
        "destinationAwsSecretAccessKey": "minio-secret",
    }

    with pytest.raises(ValidationError):
        CREATE_ADAPTER.validate_python(payload)
