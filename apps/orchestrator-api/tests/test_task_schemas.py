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
        "config": {
            "dbBackupsFilenamePrefix": "primary",
            "databaseHost": "postgresql",
            "databaseName": "app",
            "databaseUsername": "postgres",
            "databasePassword": "secret",
            "destinationAwsEndpoint": "https://minio.local",
            "destinationAwsBucketName": "backups",
            "destinationAwsAccessKeyId": "minio",
            "destinationAwsSecretAccessKey": "minio-secret",
        },
    }

    result = CREATE_ADAPTER.validate_python(payload)

    assert result.serviceType == "db_backupper"
    assert result.config.dbBackupsFilenamePrefix == "primary"
    assert result.triggerMode == "event_based"


def test_s3_task_update_schema_accepts_s3_payload() -> None:
    payload = {
        "serviceType": "s3_backupper",
        "schedule": "15 * * * *",
        "triggerMode": "scheduled",
        "config": {
            "sourceS3AwsBucketSubfolderName": "incoming",
            "destinationS3AwsBucketName": "archive",
        },
    }

    result = UPDATE_ADAPTER.validate_python(payload)

    assert result.serviceType == "s3_backupper"
    assert result.config.destinationS3AwsBucketName == "archive"


def test_env_backupper_create_schema_accepts_payload() -> None:
    payload = {
        "serviceType": "env_backupper",
        "name": "Namespace snapshot",
        "namespace": "default",
        "enabled": True,
        "schedule": "0 2 * * *",
        "triggerMode": "scheduled",
        "config": {
            "envBackupsFilenamePrefix": "namespace-default",
            "destinationAwsEndpoint": "https://minio.local",
            "destinationAwsBucketName": "backups",
            "destinationAwsAccessKeyId": "minio",
            "destinationAwsSecretAccessKey": "minio-secret",
        },
    }

    result = CREATE_ADAPTER.validate_python(payload)

    assert result.serviceType == "env_backupper"
    assert result.config.envBackupsFilenamePrefix == "namespace-default"


def test_env_restorer_create_schema_accepts_payload() -> None:
    payload = {
        "serviceType": "env_restorer",
        "name": "Namespace restore",
        "namespace": "default",
        "enabled": True,
        "schedule": None,
        "triggerMode": "manual",
        "config": {
            "envBackupsFilenamePrefix": "namespace-default",
            "sourceAwsEndpoint": "https://minio.local",
            "sourceAwsBucketName": "backups",
            "sourceAwsAccessKeyId": "minio",
            "sourceAwsSecretAccessKey": "minio-secret",
        },
    }

    result = CREATE_ADAPTER.validate_python(payload)

    assert result.serviceType == "env_restorer"
    assert result.config.envBackupsFilenamePrefix == "namespace-default"


def test_db_restorer_create_schema_accepts_payload() -> None:
    payload = {
        "serviceType": "db_restorer",
        "name": "Primary DB restore",
        "namespace": "default",
        "enabled": True,
        "schedule": None,
        "triggerMode": "manual",
        "config": {
            "dbBackupsFilenamePrefix": "primary",
            "sourceAwsEndpoint": "https://minio.local",
            "sourceAwsBucketName": "backups",
            "sourceAwsAccessKeyId": "minio",
            "sourceAwsSecretAccessKey": "minio-secret",
            "targetDatabaseHost": "postgresql",
            "targetDatabaseName": "app",
            "targetDatabaseUsername": "postgres",
            "targetDatabasePassword": "secret",
        },
    }

    result = CREATE_ADAPTER.validate_python(payload)

    assert result.serviceType == "db_restorer"
    assert result.triggerMode == "manual"
    assert result.config.targetDatabaseHost == "postgresql"


def test_s3_restorer_update_schema_accepts_payload() -> None:
    payload = {
        "serviceType": "s3_restorer",
        "triggerMode": "manual",
        "config": {
            "targetS3AwsBucketSubfolderName": "restored",
            "targetS3AwsBucketName": "target-bucket",
        },
    }

    result = UPDATE_ADAPTER.validate_python(payload)

    assert result.serviceType == "s3_restorer"
    assert result.config.targetS3AwsBucketName == "target-bucket"


def test_create_schema_rejects_fields_for_wrong_service() -> None:
    payload = {
        "serviceType": "s3_backupper",
        "name": "Broken",
        "namespace": "default",
        "enabled": False,
        "schedule": "0 0 * * *",
        "config": {
            "dbBackupsFilenamePrefix": "wrong",
            "databaseHost": "postgresql",
            "databaseName": "app",
            "databaseUsername": "postgres",
            "databasePassword": "secret",
            "destinationAwsEndpoint": "https://minio.local",
            "destinationAwsBucketName": "backups",
            "destinationAwsAccessKeyId": "minio",
            "destinationAwsSecretAccessKey": "minio-secret",
        },
    }

    with pytest.raises(ValidationError):
        CREATE_ADAPTER.validate_python(payload)
