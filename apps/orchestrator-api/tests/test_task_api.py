from __future__ import annotations


def build_db_payload(enabled: bool = False) -> dict:
    return {
        "serviceType": "db_backupper",
        "name": "Primary DB",
        "namespace": "default",
        "enabled": enabled,
        "schedule": "0 * * * *",
        "triggerMode": "scheduled",
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


def build_s3_payload(enabled: bool = False) -> dict:
    return {
        "serviceType": "s3_backupper",
        "name": "Bucket archive",
        "namespace": "default",
        "enabled": enabled,
        "schedule": "30 * * * *",
        "triggerMode": "scheduled",
        "config": {
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


def build_env_backupper_payload(enabled: bool = False) -> dict:
    return {
        "serviceType": "env_backupper",
        "name": "Namespace snapshot",
        "namespace": "default",
        "enabled": enabled,
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


def build_env_restorer_payload(enabled: bool = False) -> dict:
    return {
        "serviceType": "env_restorer",
        "name": "Namespace restore",
        "namespace": "default",
        "enabled": enabled,
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


def build_db_restorer_payload(enabled: bool = False) -> dict:
    return {
        "serviceType": "db_restorer",
        "name": "Primary DB restore",
        "namespace": "default",
        "enabled": enabled,
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


def build_s3_restorer_payload(enabled: bool = False) -> dict:
    return {
        "serviceType": "s3_restorer",
        "name": "Bucket restore",
        "namespace": "default",
        "enabled": enabled,
        "schedule": None,
        "triggerMode": "manual",
        "config": {
            "s3BackupsFilenamePrefix": "bucket-archive",
            "sourceS3AwsEndpoint": "https://source.local",
            "sourceS3AwsBucketName": "source-bucket",
            "sourceS3AwsAccessKeyId": "source-key",
            "sourceS3AwsSecretAccessKey": "source-secret",
            "targetS3AwsEndpoint": "https://destination.local",
            "targetS3AwsBucketName": "destination-bucket",
            "targetS3AwsBucketSubfolderName": "restored",
            "targetS3AwsAccessKeyId": "destination-key",
            "targetS3AwsSecretAccessKey": "destination-secret",
        },
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
    assert detail_response.json()["config"]["hasDatabasePassword"] is True
    assert detail_response.json()["watcher"]["status"] == "scheduled"

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
            "config": {"sourceS3AwsBucketSubfolderName": "processed"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["config"]["sourceS3AwsBucketSubfolderName"] == "processed"

    detail_response = client.get("/api/tasks/1")
    assert detail_response.status_code == 200
    assert detail_response.json()["config"]["hasSourceS3AwsSecretAccessKey"] is True

    disable_response = client.post("/api/tasks/1/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["lastApplyStatus"] == "disabled"

    delete_response = client.delete("/api/tasks/1")
    assert delete_response.status_code == 204


def test_env_task_api_rejects_event_based_trigger_mode(client, fake_helm) -> None:
    payload = build_env_backupper_payload(enabled=True)
    payload["triggerMode"] = "event_based"

    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 400
    assert "Event-based trigger mode is supported only" in response.json()["detail"]
    assert fake_helm.upgrade_calls == []


def test_db_task_api_rejects_manual_trigger_mode(client, fake_helm) -> None:
    payload = build_db_payload(enabled=True)
    payload["triggerMode"] = "manual"

    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 400
    assert "Manual trigger mode is supported only for restorer tasks" in response.json()["detail"]
    assert fake_helm.upgrade_calls == []


def test_env_backupper_api_lifecycle(client, fake_helm) -> None:
    create_response = client.post("/api/tasks", json=build_env_backupper_payload(enabled=True))

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["serviceType"] == "env_backupper"
    assert created["releaseName"] == "env-backupper-1"
    assert fake_helm.upgrade_calls[0]["chart_path"] == "diploma-env-backupper/ci"
    assert fake_helm.upgrade_calls[0]["values"]["extraConfigMapEnvVars"]["TARGET_NAMESPACE"] == "default"

    detail_response = client.get("/api/tasks/1")
    assert detail_response.status_code == 200
    assert detail_response.json()["config"]["envBackupsFilenamePrefix"] == "namespace-default"
    assert detail_response.json()["config"]["hasDestinationAwsSecretAccessKey"] is True

    update_response = client.patch(
        "/api/tasks/1",
        json={
            "serviceType": "env_backupper",
            "config": {"envBackupsFilenamePrefix": "namespace-archive"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["config"]["envBackupsFilenamePrefix"] == "namespace-archive"


def test_env_restorer_api_lifecycle(client, fake_helm, fake_kube) -> None:
    create_response = client.post("/api/tasks", json=build_env_restorer_payload(enabled=True))

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["serviceType"] == "env_restorer"
    assert created["releaseName"] == "env-restorer-1"
    assert created["schedule"] is None
    assert created["triggerMode"] == "manual"
    assert fake_helm.upgrade_calls[0]["chart_path"] == "diploma-env-restorer/ci"
    assert fake_helm.upgrade_calls[0]["values"]["extraConfigMapEnvVars"]["SOURCE_ENV_AWS_BUCKET_NAME"] == "backups"
    assert "BACKUPS_SCHEDULE" not in fake_helm.upgrade_calls[0]["values"]["extraConfigMapEnvVars"]

    run_response = client.post("/api/tasks/1/run")
    assert run_response.status_code == 200
    assert fake_kube.created_jobs == [("default", "env-restorer-1", "manual")]

    detail_response = client.get("/api/tasks/1")
    assert detail_response.status_code == 200
    assert detail_response.json()["config"]["envBackupsFilenamePrefix"] == "namespace-default"
    assert detail_response.json()["config"]["hasSourceAwsSecretAccessKey"] is True

    update_response = client.patch(
        "/api/tasks/1",
        json={
            "serviceType": "env_restorer",
            "config": {"envBackupsFilenamePrefix": "namespace-archive"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["config"]["envBackupsFilenamePrefix"] == "namespace-archive"

    disable_response = client.post("/api/tasks/1/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["lastApplyStatus"] == "disabled"


def test_db_restorer_api_lifecycle(client, fake_helm, fake_kube) -> None:
    create_response = client.post("/api/tasks", json=build_db_restorer_payload(enabled=True))

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["serviceType"] == "db_restorer"
    assert created["triggerMode"] == "manual"
    assert created["schedule"] is None
    assert created["releaseName"] == "db-restorer-1"
    assert fake_helm.upgrade_calls[0]["chart_path"] == "diploma-db-restorer/ci"
    assert fake_helm.upgrade_calls[0]["values"]["extraConfigMapEnvVars"]["SOURCE_DB_AWS_BUCKET_NAME"] == "backups"
    assert fake_helm.upgrade_calls[0]["values"]["extraConfigMapEnvVars"]["TARGET_DATABASE_HOST"] == "postgresql"

    run_response = client.post("/api/tasks/1/run")
    assert run_response.status_code == 200
    assert fake_kube.created_jobs == [("default", "db-restorer-1", "manual")]

    detail_response = client.get("/api/tasks/1")
    assert detail_response.status_code == 200
    assert detail_response.json()["config"]["hasSourceAwsSecretAccessKey"] is True
    assert detail_response.json()["config"]["hasTargetDatabasePassword"] is True

    update_response = client.patch(
        "/api/tasks/1",
        json={
            "serviceType": "db_restorer",
            "config": {"targetDatabaseName": "restored-app"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["config"]["targetDatabaseName"] == "restored-app"


def test_s3_restorer_api_lifecycle(client, fake_helm, fake_kube) -> None:
    create_response = client.post("/api/tasks", json=build_s3_restorer_payload(enabled=True))

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["serviceType"] == "s3_restorer"
    assert created["triggerMode"] == "manual"
    assert created["schedule"] is None
    assert created["releaseName"] == "s3-restorer-1"
    assert fake_helm.upgrade_calls[0]["chart_path"] == "diploma-s3-restorer/ci"
    assert fake_helm.upgrade_calls[0]["values"]["extraConfigMapEnvVars"]["SOURCE_S3_AWS_BUCKET_NAME"] == "source-bucket"
    assert fake_helm.upgrade_calls[0]["values"]["extraConfigMapEnvVars"]["TARGET_S3_AWS_BUCKET_NAME"] == "destination-bucket"

    run_response = client.post("/api/tasks/1/run")
    assert run_response.status_code == 200
    assert fake_kube.created_jobs == [("default", "s3-restorer-1", "manual")]

    detail_response = client.get("/api/tasks/1")
    assert detail_response.status_code == 200
    assert detail_response.json()["config"]["hasSourceS3AwsSecretAccessKey"] is True
    assert detail_response.json()["config"]["hasTargetS3AwsSecretAccessKey"] is True

    update_response = client.patch(
        "/api/tasks/1",
        json={
            "serviceType": "s3_restorer",
            "config": {"targetS3AwsBucketSubfolderName": "restored-v2"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["config"]["targetS3AwsBucketSubfolderName"] == "restored-v2"
