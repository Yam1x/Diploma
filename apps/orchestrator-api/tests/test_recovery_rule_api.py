from __future__ import annotations


def build_recovery_rule_payload(enabled: bool = True) -> dict:
    return {
        "name": "Combined recovery",
        "namespace": "default",
        "enabled": enabled,
        "db": {
            "name": "Primary DB restore",
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
        "s3": {
            "name": "Bucket restore",
            "s3BackupsFilenamePrefix": "bucket-archive",
            "sourceS3AwsEndpoint": "https://source.local",
            "sourceS3AwsBucketName": "source-bucket",
            "sourceS3AwsAccessKeyId": "source-key",
            "sourceS3AwsSecretAccessKey": "source-secret",
            "targetS3AwsEndpoint": "https://destination.local",
            "targetS3AwsBucketName": "destination-bucket",
            "targetS3AwsBucketSubfolderName": "incoming",
            "targetS3AwsAccessKeyId": "destination-key",
            "targetS3AwsSecretAccessKey": "destination-secret",
        },
    }


def test_recovery_rule_api_lifecycle(client) -> None:
    create_response = client.post("/api/recovery-rules", json=build_recovery_rule_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Combined recovery"
    assert created["enabled"] is True
    assert created["db"]["name"] == "Primary DB restore"
    assert created["s3"]["name"] == "Bucket restore"
    assert created["eventWatcherStatus"] == "waiting_for_baseline"
    assert created["lastPolledAt"] is None
    assert created["lastErrorMessage"] is None

    list_response = client.get("/api/recovery-rules")
    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "Combined recovery"

    update_response = client.patch(
        "/api/recovery-rules/1",
        json={
            "name": "Combined recovery updated",
            "s3": {"targetS3AwsBucketSubfolderName": "processed"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Combined recovery updated"
    assert update_response.json()["s3"]["targetS3AwsBucketSubfolderName"] == "processed"

    disable_response = client.post("/api/recovery-rules/1/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False

    enable_response = client.post("/api/recovery-rules/1/enable")
    assert enable_response.status_code == 200
    assert enable_response.json()["enabled"] is True

    delete_response = client.delete("/api/recovery-rules/1")
    assert delete_response.status_code == 204


def test_recovery_rule_manual_run_starts_both_jobs(client, fake_kube) -> None:
    assert client.post("/api/recovery-rules", json=build_recovery_rule_payload()).status_code == 201

    response = client.post("/api/recovery-rules/1/run")

    assert response.status_code == 200
    assert ("default", "db-restorer-1", "manual") in fake_kube.created_jobs
    assert ("default", "s3-restorer-2", "manual") in fake_kube.created_jobs


def test_recovery_rule_managed_tasks_are_hidden_from_public_tasks(client) -> None:
    assert client.post("/api/recovery-rules", json=build_recovery_rule_payload()).status_code == 201

    response = client.get("/api/tasks")

    assert response.status_code == 200
    assert response.json() == []


def test_recovery_rule_delete_after_run_succeeds(client, fake_kube) -> None:
    assert client.post("/api/recovery-rules", json=build_recovery_rule_payload()).status_code == 201
    assert client.post("/api/recovery-rules/1/run").status_code == 200

    delete_response = client.delete("/api/recovery-rules/1")

    assert delete_response.status_code == 204
