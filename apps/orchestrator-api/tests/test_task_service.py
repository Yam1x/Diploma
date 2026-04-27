from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.task import ServiceType, Task, TaskSecret, TriggerMode


def build_db_event_task() -> Task:
    task = Task(
        name="Primary DB",
        namespace="default",
        service_type=ServiceType.DB_BACKUPPER,
        enabled=True,
        schedule="0 * * * *",
        trigger_mode=TriggerMode.EVENT_BASED.value,
        release_name="db-backupper-7",
        db_backups_filename_prefix="primary",
        database_host="postgresql",
        database_name="app",
        database_username="postgres",
        destination_aws_endpoint="https://minio.local",
        destination_aws_bucket_name="backups",
        destination_aws_access_key_id="minio",
    )
    task.secret = TaskSecret(
        database_password_encrypted="secret",
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
        s3_backups_filename_prefix="bucket",
        source_s3_aws_endpoint="https://source.local",
        source_s3_aws_access_key_id="source-key",
        source_s3_aws_bucket_name="source-bucket",
        source_s3_aws_bucket_subfolder_name="incoming",
        destination_s3_aws_endpoint="https://destination.local",
        destination_s3_aws_access_key_id="destination-key",
        destination_s3_aws_bucket_name="destination-bucket",
    )
    task.secret = TaskSecret(
        source_s3_aws_secret_access_key_encrypted="source-secret",
        destination_s3_aws_secret_access_key_encrypted="destination-secret",
    )
    return task


def test_release_names_use_service_specific_prefix(service) -> None:
    assert service._build_release_name(12, ServiceType.DB_BACKUPPER) == "db-backupper-12"
    assert service._build_release_name(12, ServiceType.S3_BACKUPPER) == "s3-backupper-12"


def test_build_values_for_s3_task(service) -> None:
    task = build_s3_task()
    config = service._get_deployment_config(ServiceType.S3_BACKUPPER, service.settings)

    values = service._build_values(task, config)

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


def test_validate_required_s3_secrets_requires_both_keys(service) -> None:
    task = build_s3_task()
    task.secret.source_s3_aws_secret_access_key_encrypted = None

    with pytest.raises(HTTPException) as exc:
        service._validate_required_secrets(task)

    assert exc.value.status_code == 400
    assert "Source S3 AWS secret access key" in exc.value.detail


def test_validate_trigger_mode_rejects_public_event_based_for_s3(service) -> None:
    with pytest.raises(HTTPException) as exc:
        service._validate_trigger_mode(ServiceType.S3_BACKUPPER, "event_based")

    assert exc.value.status_code == 400
    assert "configured only through event rules" in exc.value.detail


def test_build_db_job_spec_adds_pgpassword_for_manual_jobs(service) -> None:
    task = build_db_event_task()
    config = service._get_deployment_config(ServiceType.DB_BACKUPPER, service.settings)

    spec = service._build_db_job_spec(task, config)

    env = {item["name"]: item["value"] for item in spec["template"]["spec"]["containers"][0]["env"]}
    assert env["DATABASE_PASSWORD"] == "secret"
    assert env["PGPASSWORD"] == "secret"
