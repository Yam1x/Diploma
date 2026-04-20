from __future__ import annotations


def build_db_payload(name: str = "Primary DB", enabled: bool = True) -> dict:
    return {
        "serviceType": "db_backupper",
        "name": name,
        "namespace": "default",
        "enabled": enabled,
        "schedule": None,
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


def build_s3_payload(name: str = "Bucket archive", enabled: bool = True) -> dict:
    return {
        "serviceType": "s3_backupper",
        "name": name,
        "namespace": "default",
        "enabled": enabled,
        "schedule": None,
        "triggerMode": "event_based",
        "s3BackupsFilenamePrefix": "bucket-archive",
        "sourceS3AwsEndpoint": "https://source.local",
        "sourceS3AwsAccessKeyId": "source-key",
        "sourceS3AwsBucketName": "source-bucket",
        "sourceS3AwsBucketSubfolderName": "incoming",
        "sourceS3AwsSecretAccessKey": "source-secret",
        "destinationS3AwsEndpoint": "https://destination.local",
        "destinationS3AwsAccessKeyId": "destination-key",
        "destinationS3AwsBucketName": "destination-bucket",
        "destinationS3AwsSecretAccessKey": "destination-secret",
    }


def build_rule_payload(enabled: bool = True, db_task_id: int = 1, s3_task_id: int = 2) -> dict:
    return {
        "name": "Combined backup",
        "enabled": enabled,
        "dbTaskId": db_task_id,
        "s3TaskId": s3_task_id,
    }


def test_event_rule_api_lifecycle(client) -> None:
    assert client.post("/api/tasks", json=build_db_payload()).status_code == 201
    assert client.post("/api/tasks", json=build_s3_payload()).status_code == 201

    create_response = client.post("/api/event-rules", json=build_rule_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Combined backup"
    assert created["enabled"] is True
    assert created["dbTaskName"] == "Primary DB"
    assert created["s3TaskName"] == "Bucket archive"
    assert created["eventWatcherStatus"] == "waiting_for_baseline"

    list_response = client.get("/api/event-rules")
    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "Combined backup"

    update_response = client.patch(
        "/api/event-rules/1",
        json={
            "name": "Combined backup updated",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Combined backup updated"

    disable_response = client.post("/api/event-rules/1/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False

    enable_response = client.post("/api/event-rules/1/enable")
    assert enable_response.status_code == 200
    assert enable_response.json()["enabled"] is True

    delete_response = client.delete("/api/event-rules/1")
    assert delete_response.status_code == 204


def test_event_rule_rejects_wrong_task_types(client) -> None:
    assert client.post("/api/tasks", json=build_db_payload()).status_code == 201
    assert client.post("/api/tasks", json=build_db_payload(name="Secondary DB")).status_code == 201

    response = client.post("/api/event-rules", json=build_rule_payload(s3_task_id=2))

    assert response.status_code == 400
    assert "s3_backupper" in response.json()["detail"]


def test_event_rule_rejects_disabled_or_not_deployed_tasks(client) -> None:
    assert client.post("/api/tasks", json=build_db_payload(enabled=False)).status_code == 201
    assert client.post("/api/tasks", json=build_s3_payload()).status_code == 201

    response = client.post("/api/event-rules", json=build_rule_payload(db_task_id=1, s3_task_id=2))

    assert response.status_code == 400
    assert "enabled" in response.json()["detail"]


def test_manual_event_rule_run_starts_both_jobs(client, fake_kube) -> None:
    assert client.post("/api/tasks", json=build_db_payload()).status_code == 201
    assert client.post("/api/tasks", json=build_s3_payload()).status_code == 201
    assert client.post("/api/event-rules", json=build_rule_payload()).status_code == 201

    response = client.post("/api/event-rules/1/run")

    assert response.status_code == 200
    assert ("default", "db-backupper-1", "manual") in fake_kube.created_jobs
    assert ("default", "s3-backupper-2", "manual") in fake_kube.created_jobs
