from __future__ import annotations


def build_db_payload(enabled: bool = False) -> dict:
    return {
        "serviceType": "db_backupper",
        "name": "Primary DB",
        "namespace": "default",
        "enabled": enabled,
        "schedule": "0 * * * *",
        "triggerMode": "scheduled",
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


def build_s3_payload(enabled: bool = False) -> dict:
    return {
        "serviceType": "s3_backupper",
        "name": "Bucket archive",
        "namespace": "default",
        "enabled": enabled,
        "schedule": "30 * * * *",
        "triggerMode": "scheduled",
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


def test_service_discovery_api(client) -> None:
    response = client.get("/api/namespaces/default/service-discovery")

    assert response.status_code == 200
    payload = response.json()
    services = {service["name"]: service for service in payload["services"]}

    assert services["postgresql"]["host"] == "postgresql"
    assert services["postgresql"]["ports"] == [{"name": "postgresql", "port": 5432}]
    assert services["postgresql"]["endpoints"] == [{"label": "postgresql:5432 (postgresql)", "value": "http://postgresql:5432"}]
    assert services["minio"]["endpoints"][0] == {"label": "minio:9000 (api)", "value": "http://minio:9000"}
    assert services["secure-s3"]["endpoints"][0] == {"label": "secure-s3:443 (https)", "value": "https://secure-s3"}


def test_db_task_api_lifecycle(client, fake_helm) -> None:
    create_response = client.post("/api/tasks", json=build_db_payload(enabled=True))

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["serviceType"] == "db_backupper"
    assert created["triggerMode"] == "scheduled"
    assert created["releaseName"] == "db-backupper-1"
    assert fake_helm.upgrade_calls[0]["chart_path"] == "diploma-db-backupper/ci"
    assert fake_helm.upgrade_calls[0]["values"]["extraConfigMapEnvVars"]["DATABASE_NAME"] == "app"

    list_response = client.get("/api/tasks")
    assert list_response.status_code == 200
    assert list_response.json()[0]["serviceType"] == "db_backupper"

    detail_response = client.get("/api/tasks/1")
    assert detail_response.status_code == 200
    assert detail_response.json()["hasDatabasePassword"] is True
    assert detail_response.json()["eventWatcherStatus"] == "scheduled"

    update_response = client.patch(
        "/api/tasks/1",
        json={
            "serviceType": "db_backupper",
            "name": "Primary DB Updated",
            "schedule": "15 * * * *",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Primary DB Updated"

    refresh_response = client.post("/api/tasks/1/refresh")
    assert refresh_response.status_code == 200
    assert refresh_response.json()["lastApplyStatus"] == "deployed"

    disable_response = client.post("/api/tasks/1/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["lastApplyStatus"] == "disabled"


def test_s3_task_api_lifecycle(client, fake_helm) -> None:
    create_response = client.post("/api/tasks", json=build_s3_payload())

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["serviceType"] == "s3_backupper"
    assert created["triggerMode"] == "scheduled"
    assert created["releaseName"] == "s3-backupper-1"

    enable_response = client.post("/api/tasks/1/enable")
    assert enable_response.status_code == 200
    enabled = enable_response.json()
    assert enabled["lastApplyStatus"] == "deployed"
    assert fake_helm.upgrade_calls[0]["chart_path"] == "diploma-s3-backupper/ci"
    assert fake_helm.upgrade_calls[0]["values"]["extraConfigMapEnvVars"]["SOURCE_S3_AWS_BUCKET_NAME"] == "source-bucket"

    update_response = client.patch(
        "/api/tasks/1",
        json={
            "serviceType": "s3_backupper",
            "sourceS3AwsBucketSubfolderName": "processed",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["sourceS3AwsBucketSubfolderName"] == "processed"

    detail_response = client.get("/api/tasks/1")
    assert detail_response.status_code == 200
    assert detail_response.json()["hasSourceS3AwsSecretAccessKey"] is True

    disable_response = client.post("/api/tasks/1/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["lastApplyStatus"] == "disabled"

    delete_response = client.delete("/api/tasks/1")
    assert delete_response.status_code == 204


def test_db_task_api_accepts_event_based_trigger_mode(client, fake_helm) -> None:
    payload = build_db_payload(enabled=True)
    payload["triggerMode"] = "event_based"

    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 201
    created = response.json()
    assert created["triggerMode"] == "event_based"
    assert created["eventWatcherStatus"] == "waiting_for_baseline"
    assert fake_helm.upgrade_calls[0]["values"]["extraConfigMapEnvVars"]["DATABASE_NAME"] == "app"


def test_non_db_task_rejects_event_based_trigger_mode(client) -> None:
    payload = build_s3_payload()
    payload["triggerMode"] = "event_based"

    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 400
    assert "Event-based trigger mode" in response.json()["detail"]
