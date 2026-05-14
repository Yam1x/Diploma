from __future__ import annotations

from app.services.event_rule_service import EventRuleService


def build_rule_payload(enabled: bool = True) -> dict:
    return {
        "name": "Combined backup",
        "namespace": "default",
        "enabled": enabled,
        "dbConfig": {
            "name": "Primary DB",
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
        "s3Config": {
            "name": "Bucket archive",
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
        },
    }


def test_event_rule_api_lifecycle(client) -> None:
    create_response = client.post("/api/event-rules", json=build_rule_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Combined backup"
    assert created["enabled"] is True
    assert created["dbConfig"]["name"] == "Primary DB"
    assert created["s3Config"]["name"] == "Bucket archive"
    assert created["watcher"]["status"] == "waiting_for_baseline"

    list_response = client.get("/api/event-rules")
    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "Combined backup"

    update_response = client.patch(
        "/api/event-rules/1",
        json={
            "name": "Combined backup updated",
            "dbConfig": {"databaseName": "app_updated"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Combined backup updated"
    assert update_response.json()["dbConfig"]["databaseName"] == "app_updated"

    disable_response = client.post("/api/event-rules/1/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False

    enable_response = client.post("/api/event-rules/1/enable")
    assert enable_response.status_code == 200
    assert enable_response.json()["enabled"] is True

    delete_response = client.delete("/api/event-rules/1")
    assert delete_response.status_code == 204


def test_manual_event_rule_run_starts_both_jobs(client, fake_kube) -> None:
    assert client.post("/api/event-rules", json=build_rule_payload()).status_code == 201

    response = client.post("/api/event-rules/1/run")

    assert response.status_code == 200
    assert ("default", EventRuleService._db_release_name(1), "manual") in fake_kube.created_jobs
    assert ("default", EventRuleService._s3_release_name(1), "manual") in fake_kube.created_jobs
