from __future__ import annotations

from app.services.recovery_rule_service import RecoveryEventRuleService


def build_recovery_rule_payload(enabled: bool = True) -> dict:
    return {
        "name": "Combined recovery",
        "namespace": "default",
        "enabled": enabled,
        "dbConfig": {
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
        "s3Config": {
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
    assert created["dbConfig"]["name"] == "Primary DB restore"
    assert created["s3Config"]["name"] == "Bucket restore"
    assert created["watcher"]["status"] == "waiting_for_baseline"
    assert created["watcher"]["lastPolledAt"] is None
    assert created["watcher"]["lastErrorMessage"] is None

    list_response = client.get("/api/recovery-rules")
    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "Combined recovery"

    update_response = client.patch(
        "/api/recovery-rules/1",
        json={
            "name": "Combined recovery updated",
            "s3Config": {"targetS3AwsBucketSubfolderName": "processed"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Combined recovery updated"
    assert update_response.json()["s3Config"]["targetS3AwsBucketSubfolderName"] == "processed"

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
    assert ("default", RecoveryEventRuleService._db_release_name(1), "manual") in fake_kube.created_jobs
    assert ("default", RecoveryEventRuleService._s3_release_name(1), "manual") in fake_kube.created_jobs


def test_recovery_rule_manual_db_run_starts_only_db_job(client, fake_kube) -> None:
    assert client.post("/api/recovery-rules", json=build_recovery_rule_payload()).status_code == 201

    response = client.post("/api/recovery-rules/1/run/db")

    assert response.status_code == 200
    assert fake_kube.created_jobs == [("default", RecoveryEventRuleService._db_release_name(1), "manual")]


def test_recovery_rule_manual_s3_run_starts_only_s3_job(client, fake_kube) -> None:
    assert client.post("/api/recovery-rules", json=build_recovery_rule_payload()).status_code == 201

    response = client.post("/api/recovery-rules/1/run/s3")

    assert response.status_code == 200
    assert fake_kube.created_jobs == [("default", RecoveryEventRuleService._s3_release_name(1), "manual")]


def test_recovery_rule_has_no_hidden_public_tasks(client) -> None:
    assert client.post("/api/recovery-rules", json=build_recovery_rule_payload()).status_code == 201

    response = client.get("/api/tasks")

    assert response.status_code == 200
    assert response.json() == []


def test_recovery_rule_delete_after_run_succeeds(client, fake_kube) -> None:
    assert client.post("/api/recovery-rules", json=build_recovery_rule_payload()).status_code == 201
    assert client.post("/api/recovery-rules/1/run").status_code == 200

    delete_response = client.delete("/api/recovery-rules/1")

    assert delete_response.status_code == 204
