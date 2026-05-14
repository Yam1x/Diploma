from __future__ import annotations


def build_rule_payload(enabled: bool = True) -> dict:
    return {
        "name": "Combined backup",
        "namespace": "default",
        "enabled": enabled,
        "db": {
            "backupsFilenamePrefix": "primary",
            "host": "postgresql",
            "name": "app",
            "username": "postgres",
            "password": "secret",
            "destinationEndpoint": "https://minio.local",
            "destinationBucketName": "backups",
            "destinationAccessKeyId": "minio",
            "destinationSecretAccessKey": "minio-secret",
        },
        "s3": {
            "backupsFilenamePrefix": "bucket-archive",
            "sourceEndpoint": "https://source.local",
            "sourceBucketName": "source-bucket",
            "sourceAccessKeyId": "source-key",
            "sourceSecretAccessKey": "source-secret",
            "sourceSubfolderName": "incoming",
            "destinationEndpoint": "https://destination.local",
            "destinationBucketName": "destination-bucket",
            "destinationAccessKeyId": "destination-key",
            "destinationSecretAccessKey": "destination-secret",
        },
    }


def test_event_rule_api_lifecycle(client) -> None:
    create_response = client.post("/api/event-rules", json=build_rule_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Combined backup"
    assert created["enabled"] is True
    assert created["db"]["databaseName"] == "app"
    assert created["s3"]["sourceBucketName"] == "source-bucket"
    assert created["eventWatcherStatus"] == "waiting_for_baseline"

    list_response = client.get("/api/event-rules")
    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "Combined backup"

    update_response = client.patch(
        "/api/event-rules/1",
        json={
            "name": "Combined backup updated",
            "db": {"name": "app_updated"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Combined backup updated"
    assert update_response.json()["db"]["databaseName"] == "app_updated"

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
    assert ("default", "db-backupper-1", "manual") in fake_kube.created_jobs
    assert ("default", "s3-backupper-2", "manual") in fake_kube.created_jobs