from __future__ import annotations


def build_db_payload(enabled: bool = False) -> dict:
    return {
        "serviceType": "db_backupper",
        "name": "Primary DB",
        "namespace": "default",
        "enabled": enabled,
        "schedule": "0 * * * *",
        "triggerMode": "scheduled",
        "filenamePrefix": "primary",
        "source": {
            "host": "postgresql",
            "name": "app",
            "username": "postgres",
            "password": "secret",
        },
        "destination": {
            "endpoint": "https://minio.local",
            "bucketName": "backups",
            "accessKeyId": "minio",
            "secretAccessKey": "minio-secret",
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
        "filenamePrefix": "bucket-archive",
        "source": {
            "endpoint": "https://source.local",
            "bucketName": "source-bucket",
            "accessKeyId": "source-key",
            "secretAccessKey": "source-secret",
            "subfolderName": "incoming",
        },
        "destination": {
            "endpoint": "https://destination.local",
            "bucketName": "destination-bucket",
            "accessKeyId": "destination-key",
            "secretAccessKey": "destination-secret",
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
        "filenamePrefix": "namespace-default",
        "destination": {
            "endpoint": "https://minio.local",
            "bucketName": "backups",
            "accessKeyId": "minio",
            "secretAccessKey": "minio-secret",
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
        "filenamePrefix": "namespace-default",
        "source": {
            "endpoint": "https://minio.local",
            "bucketName": "backups",
            "accessKeyId": "minio",
            "secretAccessKey": "minio-secret",
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
        "filenamePrefix": "primary",
        "source": {
            "endpoint": "https://minio.local",
            "bucketName": "backups",
            "accessKeyId": "minio",
            "secretAccessKey": "minio-secret",
        },
        "destination": {
            "host": "postgresql",
            "name": "app",
            "username": "postgres",
            "password": "secret",
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
        "filenamePrefix": "bucket-archive",
        "source": {
            "endpoint": "https://source.local",
            "bucketName": "source-bucket",
            "accessKeyId": "source-key",
            "secretAccessKey": "source-secret",
        },
        "destination": {
            "endpoint": "https://destination.local",
            "bucketName": "destination-bucket",
            "accessKeyId": "destination-key",
            "secretAccessKey": "destination-secret",
            "subfolderName": "restored",
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
    assert detail_response.json()["hasSourcePassword"] is True
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
            "source": {"subfolderName": "processed"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["sourceSubfolderName"] == "processed"

    detail_response = client.get("/api/tasks/1")
    assert detail_response.status_code == 200
    assert detail_response.json()["hasSourceSecret"] is True

    disable_response = client.post("/api/tasks/1/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["lastApplyStatus"] == "disabled"

    delete_response = client.delete("/api/tasks/1")
    assert delete_response.status_code == 204


def test_db_task_api_rejects_event_based_trigger_mode(client, fake_helm) -> None:
    payload = build_db_payload(enabled=True)
    payload["triggerMode"] = "event_based"

    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 400
    assert "configured only through event rules" in response.json()["detail"]
    assert fake_helm.upgrade_calls == []


def test_s3_task_api_rejects_event_based_trigger_mode(client, fake_helm) -> None:
    payload = build_s3_payload()
    payload["triggerMode"] = "event_based"

    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 400
    assert "configured only through event rules" in response.json()["detail"]
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
    assert detail_response.json()["filenamePrefix"] == "namespace-default"
    assert detail_response.json()["hasDestinationSecret"] is True

    update_response = client.patch(
        "/api/tasks/1",
        json={
            "serviceType": "env_backupper",
            "filenamePrefix": "namespace-archive",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["filenamePrefix"] == "namespace-archive"


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
    assert detail_response.json()["filenamePrefix"] == "namespace-default"
    assert detail_response.json()["hasSourceSecret"] is True

    update_response = client.patch(
        "/api/tasks/1",
        json={
            "serviceType": "env_restorer",
            "filenamePrefix": "namespace-archive",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["filenamePrefix"] == "namespace-archive"

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
    assert detail_response.json()["hasSourceSecret"] is True
    assert detail_response.json()["hasDestinationPassword"] is True

    update_response = client.patch(
        "/api/tasks/1",
        json={
            "serviceType": "db_restorer",
            "destination": {"name": "restored-app"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["destinationName"] == "restored-app"


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
    assert detail_response.json()["hasSourceSecret"] is True
    assert detail_response.json()["hasDestinationSecret"] is True

    update_response = client.patch(
        "/api/tasks/1",
        json={
            "serviceType": "s3_restorer",
            "destination": {"subfolderName": "restored-v2"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["destinationSubfolderName"] == "restored-v2"