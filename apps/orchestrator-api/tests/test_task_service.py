from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.task import (
    DbBackupTaskConfig,
    DbRestoreTaskConfig,
    EnvBackupTaskConfig,
    EnvRestoreTaskConfig,
    S3BackupTaskConfig,
    S3RestoreTaskConfig,
    ServiceType,
    Task,
    TriggerMode,
)


def build_db_event_task() -> Task:
    task = Task(
        name="Primary DB",
        namespace="default",
        service_type=ServiceType.DB_BACKUPPER,
        enabled=True,
        schedule="0 * * * *",
        trigger_mode=TriggerMode.EVENT_BASED.value,
        release_name="db-backupper-7",
    )
    task.db_backup_config = DbBackupTaskConfig(
        db_backups_filename_prefix="primary",
        database_host="postgresql",
        database_name="app",
        database_username="postgres",
        database_password_encrypted="secret",
        destination_aws_endpoint="https://minio.local",
        destination_aws_bucket_name="backups",
        destination_aws_access_key_id="minio",
        destination_aws_secret_access_key_encrypted="minio-secret",
    )
    return task


def build_s3_task() -> Task:
    task = Task(
        name="Bucket archive",
        namespace="default",
        service_type=ServiceType.S3_BACKUPPER,
        enabled=False,
        schedule="0 * * * *",
        trigger_mode=TriggerMode.SCHEDULED.value,
        release_name="s3-backupper-7",
    )
    task.s3_backup_config = S3BackupTaskConfig(
        s3_backups_filename_prefix="bucket",
        source_s3_aws_endpoint="https://source.local",
        source_s3_aws_access_key_id="source-key",
        source_s3_aws_bucket_name="source-bucket",
        source_s3_aws_bucket_subfolder_name="incoming",
        source_s3_aws_secret_access_key_encrypted="source-secret",
        destination_s3_aws_endpoint="https://destination.local",
        destination_s3_aws_access_key_id="destination-key",
        destination_s3_aws_bucket_name="destination-bucket",
        destination_s3_aws_secret_access_key_encrypted="destination-secret",
    )
    return task


def build_env_backupper_task() -> Task:
    task = Task(
        name="Namespace snapshot",
        namespace="default",
        service_type=ServiceType.ENV_BACKUPPER,
        enabled=True,
        schedule="0 2 * * *",
        trigger_mode=TriggerMode.SCHEDULED.value,
        release_name="env-backupper-9",
    )
    task.env_backup_config = EnvBackupTaskConfig(
        env_backups_filename_prefix="namespace-default",
        destination_aws_endpoint="https://minio.local",
        destination_aws_bucket_name="backups",
        destination_aws_access_key_id="minio",
        destination_aws_secret_access_key_encrypted="minio-secret",
    )
    return task


def build_env_restorer_task() -> Task:
    task = Task(
        name="Namespace restore",
        namespace="default",
        service_type=ServiceType.ENV_RESTORER,
        enabled=True,
        schedule=None,
        trigger_mode=TriggerMode.MANUAL.value,
        release_name="env-restorer-10",
    )
    task.env_restore_config = EnvRestoreTaskConfig(
        env_backups_filename_prefix="namespace-default",
        source_aws_endpoint="https://minio.local",
        source_aws_bucket_name="backups",
        source_aws_access_key_id="minio",
        source_aws_secret_access_key_encrypted="minio-secret",
    )
    return task


def build_db_restorer_task() -> Task:
    task = Task(
        name="Primary DB restore",
        namespace="default",
        service_type=ServiceType.DB_RESTORER,
        enabled=True,
        schedule=None,
        trigger_mode=TriggerMode.MANUAL.value,
        release_name="db-restorer-11",
    )
    task.db_restore_config = DbRestoreTaskConfig(
        db_backups_filename_prefix="primary",
        source_aws_endpoint="https://minio.local",
        source_aws_bucket_name="backups",
        source_aws_access_key_id="minio",
        source_aws_secret_access_key_encrypted="minio-secret",
        target_database_host="postgresql",
        target_database_name="app",
        target_database_username="postgres",
        target_database_password_encrypted="secret",
    )
    return task


def build_s3_restorer_task() -> Task:
    task = Task(
        name="Bucket restore",
        namespace="default",
        service_type=ServiceType.S3_RESTORER,
        enabled=True,
        schedule=None,
        trigger_mode=TriggerMode.MANUAL.value,
        release_name="s3-restorer-12",
    )
    task.s3_restore_config = S3RestoreTaskConfig(
        s3_backups_filename_prefix="bucket",
        source_s3_aws_endpoint="https://source.local",
        source_s3_aws_bucket_name="source-bucket",
        source_s3_aws_access_key_id="source-key",
        source_s3_aws_secret_access_key_encrypted="source-secret",
        target_s3_aws_endpoint="https://target.local",
        target_s3_aws_bucket_name="target-bucket",
        target_s3_aws_bucket_subfolder_name="restored",
        target_s3_aws_access_key_id="target-key",
        target_s3_aws_secret_access_key_encrypted="target-secret",
    )
    return task


def test_release_names_use_service_specific_prefix(service) -> None:
    assert service._build_release_name(12, ServiceType.DB_BACKUPPER) == "db-backupper-12"
    assert service._build_release_name(12, ServiceType.S3_BACKUPPER) == "s3-backupper-12"
    assert service._build_release_name(12, ServiceType.ENV_BACKUPPER) == "env-backupper-12"
    assert service._build_release_name(12, ServiceType.DB_RESTORER) == "db-restorer-12"
    assert service._build_release_name(12, ServiceType.S3_RESTORER) == "s3-restorer-12"
    assert service._build_release_name(12, ServiceType.ENV_RESTORER) == "env-restorer-12"


def test_build_values_for_s3_task(service) -> None:
    task = build_s3_task()

    values = service.build_values_for_config(
        service_type=ServiceType.S3_BACKUPPER,
        namespace=task.namespace,
        trigger_mode=task.trigger_mode,
        schedule=task.schedule,
        config=task.s3_backup_config,
    )

    assert values["image"]["repository"] == service.settings.s3_backupper_image_repository
    assert values["extraConfigMapEnvVars"]["SOURCE_S3_AWS_BUCKET_NAME"] == "source-bucket"
    assert values["extraConfigMapEnvVars"]["DESTINATION_S3_AWS_BUCKET_NAME"] == "destination-bucket"


def test_build_discovered_service_generates_host_and_endpoints(service) -> None:
    discovered = service._build_discovered_service(
        {
            "name": "minio",
            "ports": [
                {"name": "api", "port": 9000},
                {"name": "https", "port": 443},
            ],
        }
    )

    assert discovered.name == "minio"
    assert discovered.host == "minio"
    assert [endpoint.value for endpoint in discovered.endpoints] == ["http://minio:9000", "https://minio"]
    assert [endpoint.label for endpoint in discovered.endpoints] == ["minio:9000 (api)", "minio:443 (https)"]


def test_build_values_for_env_backupper_task(service) -> None:
    task = build_env_backupper_task()

    values = service.build_values_for_config(
        service_type=ServiceType.ENV_BACKUPPER,
        namespace=task.namespace,
        trigger_mode=task.trigger_mode,
        schedule=task.schedule,
        config=task.env_backup_config,
    )

    assert values["image"]["repository"] == service.settings.env_backupper_image_repository
    assert values["extraConfigMapEnvVars"]["TARGET_NAMESPACE"] == "default"
    assert values["extraConfigMapEnvVars"]["ENV_BACKUPS_FILENAME_PREFIX"] == "namespace-default"


def test_build_values_for_env_restorer_task(service) -> None:
    task = build_env_restorer_task()

    values = service.build_values_for_config(
        service_type=ServiceType.ENV_RESTORER,
        namespace=task.namespace,
        trigger_mode=task.trigger_mode,
        schedule=task.schedule,
        config=task.env_restore_config,
    )

    assert values["image"]["repository"] == service.settings.env_restorer_image_repository
    assert values["extraConfigMapEnvVars"]["TARGET_NAMESPACE"] == "default"
    assert values["extraConfigMapEnvVars"]["SOURCE_ENV_AWS_BUCKET_NAME"] == "backups"
    assert "BACKUPS_SCHEDULE" not in values["extraConfigMapEnvVars"]


def test_build_values_for_db_restorer_task(service) -> None:
    task = build_db_restorer_task()

    values = service.build_values_for_config(
        service_type=ServiceType.DB_RESTORER,
        namespace=task.namespace,
        trigger_mode=task.trigger_mode,
        schedule=task.schedule,
        config=task.db_restore_config,
    )

    assert values["image"]["repository"] == service.settings.db_restorer_image_repository
    assert values["extraConfigMapEnvVars"]["SOURCE_DB_AWS_BUCKET_NAME"] == "backups"
    assert values["extraConfigMapEnvVars"]["TARGET_DATABASE_HOST"] == "postgresql"
    assert "BACKUPS_SCHEDULE" not in values["extraConfigMapEnvVars"]


def test_build_values_for_s3_restorer_task(service) -> None:
    task = build_s3_restorer_task()

    values = service.build_values_for_config(
        service_type=ServiceType.S3_RESTORER,
        namespace=task.namespace,
        trigger_mode=task.trigger_mode,
        schedule=task.schedule,
        config=task.s3_restore_config,
    )

    assert values["image"]["repository"] == service.settings.s3_restorer_image_repository
    assert values["extraConfigMapEnvVars"]["SOURCE_S3_AWS_BUCKET_NAME"] == "source-bucket"
    assert values["extraConfigMapEnvVars"]["TARGET_S3_AWS_BUCKET_SUBFOLDER_NAME"] == "restored"
    assert "BACKUPS_SCHEDULE" not in values["extraConfigMapEnvVars"]


def test_validate_required_s3_secrets_requires_both_keys(service) -> None:
    task = build_s3_task()
    task.s3_backup_config.source_s3_aws_secret_access_key_encrypted = None

    with pytest.raises(HTTPException) as exc:
        service._validate_required_secrets(task)

    assert exc.value.status_code == 400
    assert "Source S3 AWS secret access key" in exc.value.detail


def test_validate_trigger_mode_rejects_event_based_for_standalone_backup_tasks(service) -> None:
    with pytest.raises(HTTPException) as exc:
        service._validate_trigger_mode(ServiceType.DB_BACKUPPER, TriggerMode.EVENT_BASED.value)

    assert exc.value.status_code == 400
    assert "Event-based trigger mode is not supported for standalone tasks" in exc.value.detail


def test_validate_trigger_mode_requires_manual_for_public_restorers(service) -> None:
    with pytest.raises(HTTPException) as exc:
        service._validate_trigger_mode(ServiceType.DB_RESTORER, TriggerMode.SCHEDULED.value)

    assert exc.value.status_code == 400
    assert "Manual trigger mode is required" in exc.value.detail


def test_normalize_schedule_clears_manual_public_recovery_schedule(service) -> None:
    task = build_db_restorer_task()
    task.schedule = "0 * * * *"

    service._normalize_schedule(task)

    assert task.schedule is None


def test_build_db_job_spec_adds_pgpassword_for_manual_jobs(service) -> None:
    task = build_db_event_task()

    spec = service.build_job_spec_for_config(
        service_type=task.service_type,
        namespace=task.namespace,
        schedule=task.schedule,
        release_name=task.release_name,
        config=task.db_backup_config,
    )

    env = {item["name"]: item["value"] for item in spec["template"]["spec"]["containers"][0]["env"]}
    assert env["DATABASE_PASSWORD"] == "secret"
    assert env["PGPASSWORD"] == "secret"


def test_build_db_restore_job_spec_adds_pgpassword_for_manual_jobs(service) -> None:
    task = build_db_restorer_task()

    spec = service.build_job_spec_for_config(
        service_type=task.service_type,
        namespace=task.namespace,
        schedule=task.schedule,
        release_name=task.release_name,
        config=task.db_restore_config,
    )

    env = {item["name"]: item["value"] for item in spec["template"]["spec"]["containers"][0]["env"]}
    assert env["TARGET_DATABASE_PASSWORD"] == "secret"
    assert env["PGPASSWORD"] == "secret"
