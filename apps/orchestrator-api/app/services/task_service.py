from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings, get_settings
from app.core.helm import HelmClient, HelmError
from app.core.kube import KubeClient, KubernetesError
from app.core.security import SecretCipher
from app.models.notification import Notification
from app.models.task import ServiceType, Task, TaskEventWatchState, TaskJobRun, TaskSecret, TriggerMode
from app.services.notification_service import NotificationService
from app.schemas.task import (
    DbTaskCreate,
    DbRestorerTaskCreate,
    DbRestorerTaskDetail,
    DbRestorerTaskSummary,
    DbRestorerTaskUpdate,
    DbTaskDetail,
    DbTaskSummary,
    DbTaskUpdate,
    EnvBackupperTaskCreate,
    EnvBackupperTaskDetail,
    EnvBackupperTaskSummary,
    EnvBackupperTaskUpdate,
    EnvRestorerTaskCreate,
    EnvRestorerTaskDetail,
    EnvRestorerTaskSummary,
    EnvRestorerTaskUpdate,
    EnvSynchronizerTaskCreate,
    EnvSynchronizerTaskDetail,
    EnvSynchronizerTaskSummary,
    EnvSynchronizerTaskUpdate,
    S3RestorerTaskCreate,
    S3RestorerTaskDetail,
    S3RestorerTaskSummary,
    S3RestorerTaskUpdate,
    S3TaskCreate,
    S3TaskDetail,
    S3TaskSummary,
    S3TaskUpdate,
    ServiceDiscoveryEndpoint,
    ServiceDiscoveryResponse,
    ServiceDiscoveryService,
    ServiceDiscoveryServicePort,
    TaskCreate,
    TaskDetail,
    TaskSummary,
    TaskUpdate,
)


@dataclass(frozen=True)
class ServiceDeploymentConfig:
    image_registry: str
    image_repository: str
    image_tag: str
    image_pull_policy: str
    chart_repository_url: str
    chart_ref: str
    chart_path: str
    release_prefix: str


def _get_nested(data: dict | None, *keys: str, default: str = "") -> str:
    if data is None:
        return default
    for key in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(key, {})
    return data if isinstance(data, str) else default


def _build_task_config(payload: TaskCreate) -> dict:
    if isinstance(payload, DbTaskCreate):
        return {
            "filenamePrefix": payload.filenamePrefix,
            "source": {
                "host": payload.source.host,
                "name": payload.source.name,
                "username": payload.source.username,
            },
            "destination": {
                "endpoint": payload.destination.endpoint,
                "bucketName": payload.destination.bucketName,
                "accessKeyId": payload.destination.accessKeyId,
            },
        }
    if isinstance(payload, S3TaskCreate):
        return {
            "filenamePrefix": payload.filenamePrefix,
            "source": {
                "endpoint": payload.source.endpoint,
                "bucketName": payload.source.bucketName,
                "accessKeyId": payload.source.accessKeyId,
                "subfolderName": payload.source.subfolderName,
            },
            "destination": {
                "endpoint": payload.destination.endpoint,
                "bucketName": payload.destination.bucketName,
                "accessKeyId": payload.destination.accessKeyId,
            },
        }
    if isinstance(payload, EnvBackupperTaskCreate):
        return {
            "filenamePrefix": payload.filenamePrefix,
            "destination": {
                "endpoint": payload.destination.endpoint,
                "bucketName": payload.destination.bucketName,
                "accessKeyId": payload.destination.accessKeyId,
            },
        }
    if isinstance(payload, DbRestorerTaskCreate):
        return {
            "filenamePrefix": payload.filenamePrefix,
            "source": {
                "endpoint": payload.source.endpoint,
                "bucketName": payload.source.bucketName,
                "accessKeyId": payload.source.accessKeyId,
            },
            "destination": {
                "host": payload.destination.host,
                "name": payload.destination.name,
                "username": payload.destination.username,
            },
        }
    if isinstance(payload, S3RestorerTaskCreate):
        return {
            "filenamePrefix": payload.filenamePrefix,
            "source": {
                "endpoint": payload.source.endpoint,
                "bucketName": payload.source.bucketName,
                "accessKeyId": payload.source.accessKeyId,
            },
            "destination": {
                "endpoint": payload.destination.endpoint,
                "bucketName": payload.destination.bucketName,
                "accessKeyId": payload.destination.accessKeyId,
                "subfolderName": payload.destination.subfolderName,
            },
        }
    if isinstance(payload, EnvRestorerTaskCreate):
        return {
            "filenamePrefix": payload.filenamePrefix,
            "source": {
                "endpoint": payload.source.endpoint,
                "bucketName": payload.source.bucketName,
                "accessKeyId": payload.source.accessKeyId,
            },
        }
    if isinstance(payload, EnvSynchronizerTaskCreate):
        return {
            "repository": payload.repository,
            "pathToHelmfile": payload.pathToHelmfile,
        }
    raise HTTPException(status_code=400, detail="Unknown task type")


def _get_secrets(payload: TaskCreate) -> tuple[str | None, str | None]:
    if isinstance(payload, DbTaskCreate):
        return payload.source.password, payload.destination.secretAccessKey
    if isinstance(payload, S3TaskCreate):
        return payload.source.secretAccessKey, payload.destination.secretAccessKey
    if isinstance(payload, EnvBackupperTaskCreate):
        return None, payload.destination.secretAccessKey
    if isinstance(payload, DbRestorerTaskCreate):
        return payload.source.secretAccessKey, payload.destination.password
    if isinstance(payload, S3RestorerTaskCreate):
        return payload.source.secretAccessKey, payload.destination.secretAccessKey
    if isinstance(payload, EnvRestorerTaskCreate):
        return payload.source.secretAccessKey, None
    return None, None


class TaskService:
    def __init__(
        self,
        db: Session,
        helm: HelmClient | None = None,
        kube: KubeClient | None = None,
        cipher: SecretCipher | None = None,
        notifications: NotificationService | None = None,
    ) -> None:
        self.db = db
        self.helm = helm or HelmClient()
        self.kube = kube or KubeClient()
        self.cipher = cipher or SecretCipher()
        self.notifications = notifications or NotificationService(db)
        self.settings = get_settings()

    def list_tasks(self) -> list[TaskSummary]:
        tasks = (
            self.db.query(Task)
            .options(joinedload(Task.secret))
            .filter(Task.managed_by_rule_id.is_(None), Task.managed_by_recovery_rule_id.is_(None))
            .order_by(Task.updated_at.desc())
            .all()
        )
        return [self._to_summary(task) for task in tasks]

    def get_task(self, task_id: int) -> TaskDetail:
        return self._to_detail(self._get_public_task_model(task_id))

    def create_task(self, payload: TaskCreate) -> TaskDetail:
        service_type = ServiceType(payload.serviceType)
        trigger_mode = self._validate_trigger_mode(service_type, payload.triggerMode)

        task = Task(
            name=payload.name,
            namespace=payload.namespace,
            enabled=False,
            service_type=service_type,
            schedule=payload.schedule,
            trigger_mode=trigger_mode.value,
            release_name="pending",
            config=_build_task_config(payload),
        )
        task.secret = TaskSecret()
        source_secret, dest_secret = _get_secrets(payload)
        task.secret.source_secret_encrypted = source_secret
        task.secret.destination_secret_encrypted = dest_secret

        self._normalize_schedule(task)
        self.db.add(task)
        self.db.flush()
        task.release_name = self._build_release_name(task.id, task.service_type)
        self.db.commit()

        if payload.enabled:
            return self.enable_task(task.id)
        return self._to_detail(self._get_task_model(task.id))

    def update_task(self, task_id: int, payload: TaskUpdate) -> TaskDetail:
        task = self._get_public_task_model(task_id)
        if payload.serviceType != task.service_type.value:
            raise HTTPException(status_code=400, detail="Changing service type is not supported")

        changes = payload.model_dump(exclude_unset=True)
        desired_enabled = changes.pop("enabled", None)
        changes.pop("serviceType", None)

        for source, target in {
            "name": "name",
            "namespace": "namespace",
            "schedule": "schedule",
            "triggerMode": "trigger_mode",
        }.items():
            if source in changes:
                value = changes[source]
                if source == "triggerMode":
                    value = self._validate_trigger_mode(task.service_type, value).value
                setattr(task, target, value)

        self._apply_config_update(task, changes)
        self._normalize_schedule(task)
        self.db.commit()

        if desired_enabled is True:
            return self.enable_task(task.id)
        if desired_enabled is False and task.enabled:
            return self.disable_task(task.id)
        if task.enabled:
            self._apply_release(task)
        return self._to_detail(self._get_task_model(task.id))

    def _apply_config_update(self, task: Task, changes: dict) -> None:
        config = dict(task.config) if task.config else {}
        updated = False

        if "filenamePrefix" in changes and changes["filenamePrefix"] is not None:
            config["filenamePrefix"] = changes["filenamePrefix"]
            updated = True

        if "source" in changes and changes["source"] is not None:
            config["source"] = {**(config.get("source", {})), **changes["source"]}
            updated = True

        if "destination" in changes and changes["destination"] is not None:
            config["destination"] = {**(config.get("destination", {})), **changes["destination"]}
            updated = True

        if "repository" in changes and changes["repository"] is not None:
            config["repository"] = changes["repository"]
            updated = True

        if "pathToHelmfile" in changes and changes["pathToHelmfile"] is not None:
            config["pathToHelmfile"] = changes["pathToHelmfile"]
            updated = True

        if updated:
            task.config = config

    def enable_task(self, task_id: int) -> TaskDetail:
        task = self._get_public_task_model(task_id)
        self.enable_task_model(task)
        return self._to_detail(self._get_public_task_model(task.id))

    def disable_task(self, task_id: int) -> TaskDetail:
        task = self._get_public_task_model(task_id)
        self.disable_task_model(task)
        return self._to_detail(task)

    def run_task(self, task_id: int) -> TaskDetail:
        task = self._get_public_task_model(task_id)
        if not task.enabled or not task.release_name:
            raise HTTPException(status_code=400, detail="Task must be deployed before running it manually")

        try:
            if task.trigger_mode == TriggerMode.EVENT_BASED.value and self._supports_event_mode(task.service_type):
                self.create_triggered_job_run(task, trigger_type="manual")
            elif task.service_type in {ServiceType.DB_RESTORER, ServiceType.S3_RESTORER, ServiceType.ENV_RESTORER}:
                job_name = self.kube.create_job(
                    task.namespace,
                    task.release_name,
                    self._build_manual_restore_job_spec(task),
                    trigger_type="manual",
                )
                task.last_apply_status = "deployed"
                task.last_apply_message = f"Manual run started: {job_name}"
                task.last_applied_at = datetime.now(timezone.utc)
                run = self._record_job_run(task, job_name, "manual")
                self.db.commit()
                self.notifications.notify_manual_run_started(task, run)
                return self._to_detail(task)
            else:
                job_name = self.kube.create_job_from_cronjob(task.namespace, task.release_name, trigger_type="manual")
                task.last_apply_status = "deployed"
                task.last_apply_message = f"Manual run started: {job_name}"
                task.last_applied_at = datetime.now(timezone.utc)
                run = self._record_job_run(task, job_name, "manual")
                self.db.commit()
                self.notifications.notify_manual_run_started(task, run)
                return self._to_detail(task)
        except KubernetesError as exc:
            task.last_apply_status = "failed"
            task.last_apply_message = str(exc)
            task.last_applied_at = datetime.now(timezone.utc)
            self.db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        self.db.commit()
        return self._to_detail(self._get_task_model(task.id))

    def refresh_task(self, task_id: int) -> TaskDetail:
        task = self._get_public_task_model(task_id)
        try:
            message = self.helm.status(task.release_name, task.namespace)
            task.last_apply_status = "deployed"
            task.last_apply_message = message
        except HelmError as exc:
            task.last_apply_status = "missing"
            task.last_apply_message = str(exc)
        task.last_applied_at = datetime.now(timezone.utc)
        self.db.commit()
        if task.last_apply_status == "missing":
            self.notifications.notify_task_missing(task)
            if task.enabled:
                self.notifications.notify_task_attention_required(task, "release_missing")
        return self._to_detail(task)

    def delete_task(self, task_id: int) -> None:
        task = self._get_public_task_model(task_id)
        self._cleanup_release(task)
        self._delete_task_model(task)
        self.db.commit()

    def list_namespaces(self) -> list[str]:
        try:
            return self.kube.list_namespaces()
        except KubernetesError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def create_namespace(self, namespace: str) -> str:
        try:
            return self.kube.create_namespace(namespace)
        except KubernetesError as exc:
            message = str(exc)
            if "already exists" in message.lower():
                raise HTTPException(status_code=409, detail=f"Namespace '{namespace}' уже существует") from exc
            raise HTTPException(status_code=502, detail=message) from exc

    def list_service_discovery(self, namespace: str) -> ServiceDiscoveryResponse:
        self._validate_namespace(namespace)
        try:
            services = self.kube.list_services(namespace)
        except KubernetesError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return ServiceDiscoveryResponse(
            services=[self._build_discovered_service(service) for service in services]
        )

    def _cleanup_release(self, task: Task) -> None:
        if not task.release_name:
            return
        try:
            self.helm.uninstall(task.release_name, task.namespace)
        except HelmError as exc:
            if self._is_missing_release_error(str(exc)):
                return
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @staticmethod
    def _is_missing_release_error(message: str) -> bool:
        lowered = message.lower()
        return "not found" in lowered or "release: not found" in lowered

    def _delete_task_model(self, task: Task) -> None:
        run_ids = select(TaskJobRun.id).where(TaskJobRun.task_id == task.id)
        (
            self.db.query(Notification)
            .filter(
                or_(
                    Notification.task_id == task.id,
                    Notification.job_run_id.in_(run_ids),
                )
            )
            .delete(synchronize_session=False)
        )
        self.db.delete(task)
        self.db.flush()

    def _apply_release(self, task: Task) -> None:
        self._validate_required_secrets(task)
        config = self._get_deployment_config(task.service_type, self.settings)
        values = self._build_values(task, config)
        try:
            message = self.helm.upgrade_install(
                task.release_name,
                task.namespace,
                values,
                chart_repository_url=config.chart_repository_url,
                chart_ref=config.chart_ref,
                chart_path=config.chart_path,
            )
            task.enabled = True
            task.last_apply_status = "deployed"
            task.last_apply_message = message or "Release applied"
            task.last_applied_at = datetime.now(timezone.utc)
            self.db.commit()
        except HelmError as exc:
            task.last_apply_status = "failed"
            task.last_apply_message = str(exc)
            task.last_applied_at = datetime.now(timezone.utc)
            self.db.commit()
            self.notifications.notify_task_deploy_failed(task)
            self.notifications.notify_task_attention_required(task, "deploy_failed")
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def enable_task_model(self, task: Task) -> None:
        self._validate_namespace(task.namespace)
        task.enabled = True
        self.db.commit()
        self._apply_release(task)

    def disable_task_model(self, task: Task) -> None:
        try:
            message = self.helm.uninstall(task.release_name, task.namespace)
            task.enabled = False
            task.last_apply_status = "disabled"
            task.last_apply_message = message or "Release removed"
            task.last_applied_at = datetime.now(timezone.utc)
            self.db.commit()
        except HelmError as exc:
            task.last_apply_status = "failed"
            task.last_apply_message = str(exc)
            task.last_applied_at = datetime.now(timezone.utc)
            self.db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def _build_values(self, task: Task, config: ServiceDeploymentConfig) -> dict:
        task_config = task.config or {}
        include_schedule = task.trigger_mode != TriggerMode.EVENT_BASED.value

        image = {
            "registry": config.image_registry,
            "repository": config.image_repository,
            "tag": config.image_tag,
            "pullPolicy": config.image_pull_policy,
        }

        resources = {
            "limits": {"cpu": "200m", "memory": "512Mi"},
            "requests": {"cpu": "1m", "memory": "256Mi"},
        }

        env = self._build_task_env(task, task_config)
        if include_schedule and task.schedule:
            env = {"BACKUPS_SCHEDULE": task.schedule, **env}

        result = {
            "image": image,
            "resources": resources,
            "triggerMode": task.trigger_mode,
            "extraConfigMapEnvVars": env,
        }

        if task.service_type in {ServiceType.ENV_BACKUPPER, ServiceType.ENV_RESTORER, ServiceType.ENV_SYNCHRONIZER}:
            result = {
                "image": image,
                "resources": resources,
                "extraConfigMapEnvVars": env,
            }
            result.pop("triggerMode", None)
            result.pop("extraConfigMapEnvVars", None)
            result["extraConfigMapEnvVars"] = env

        return result

    def _build_task_env(self, task: Task, config: dict) -> dict[str, str]:
        prefix = config.get("filenamePrefix", "")
        source = config.get("source", {})
        destination = config.get("destination", {})
        source_secret = task.secret.source_secret_encrypted if task.secret else None
        dest_secret = task.secret.destination_secret_encrypted if task.secret else None

        if task.service_type == ServiceType.DB_BACKUPPER:
            return {
                "DB_BACKUPS_FILENAME_PREFIX": prefix,
                "DATABASE_HOST": source.get("host", ""),
                "DATABASE_PASSWORD": source_secret or "",
                "DATABASE_USERNAME": source.get("username", ""),
                "DATABASE_NAME": source.get("name", ""),
                "DESTINATION_DB_AWS_ACCESS_KEY_ID": destination.get("accessKeyId", ""),
                "DESTINATION_DB_AWS_SECRET_ACCESS_KEY": dest_secret or "",
                "DESTINATION_DB_AWS_BUCKET_NAME": destination.get("bucketName", ""),
                "DESTINATION_DB_AWS_ENDPOINT": destination.get("endpoint", ""),
            }

        if task.service_type == ServiceType.DB_RESTORER:
            return {
                "DB_BACKUPS_FILENAME_PREFIX": prefix,
                "SOURCE_DB_AWS_ENDPOINT": source.get("endpoint", ""),
                "SOURCE_DB_AWS_ACCESS_KEY_ID": source.get("accessKeyId", ""),
                "SOURCE_DB_AWS_SECRET_ACCESS_KEY": source_secret or "",
                "SOURCE_DB_AWS_BUCKET_NAME": source.get("bucketName", ""),
                "TARGET_DATABASE_HOST": destination.get("host", ""),
                "TARGET_DATABASE_USERNAME": destination.get("username", ""),
                "TARGET_DATABASE_PASSWORD": dest_secret or "",
                "TARGET_DATABASE_NAME": destination.get("name", ""),
            }

        if task.service_type == ServiceType.S3_BACKUPPER:
            return {
                "S3_BACKUPS_FILENAME_PREFIX": prefix,
                "SOURCE_S3_AWS_ENDPOINT": source.get("endpoint", ""),
                "SOURCE_S3_AWS_ACCESS_KEY_ID": source.get("accessKeyId", ""),
                "SOURCE_S3_AWS_SECRET_ACCESS_KEY": source_secret or "",
                "SOURCE_S3_AWS_BUCKET_NAME": source.get("bucketName", ""),
                "SOURCE_S3_AWS_BUCKET_SUBFOLDER_NAME": source.get("subfolderName", ""),
                "DESTINATION_S3_AWS_ENDPOINT": destination.get("endpoint", ""),
                "DESTINATION_S3_AWS_ACCESS_KEY_ID": destination.get("accessKeyId", ""),
                "DESTINATION_S3_AWS_SECRET_ACCESS_KEY": dest_secret or "",
                "DESTINATION_S3_AWS_BUCKET_NAME": destination.get("bucketName", ""),
            }

        if task.service_type == ServiceType.S3_RESTORER:
            return {
                "S3_BACKUPS_FILENAME_PREFIX": prefix,
                "SOURCE_S3_AWS_ENDPOINT": source.get("endpoint", ""),
                "SOURCE_S3_AWS_ACCESS_KEY_ID": source.get("accessKeyId", ""),
                "SOURCE_S3_AWS_SECRET_ACCESS_KEY": source_secret or "",
                "SOURCE_S3_AWS_BUCKET_NAME": source.get("bucketName", ""),
                "TARGET_S3_AWS_ENDPOINT": destination.get("endpoint", ""),
                "TARGET_S3_AWS_ACCESS_KEY_ID": destination.get("accessKeyId", ""),
                "TARGET_S3_AWS_SECRET_ACCESS_KEY": dest_secret or "",
                "TARGET_S3_AWS_BUCKET_NAME": destination.get("bucketName", ""),
                "TARGET_S3_AWS_BUCKET_SUBFOLDER_NAME": destination.get("subfolderName", ""),
            }

        if task.service_type == ServiceType.ENV_BACKUPPER:
            return {
                "TARGET_NAMESPACE": task.namespace,
                "ENV_BACKUPS_FILENAME_PREFIX": prefix,
                "DESTINATION_ENV_AWS_ENDPOINT": destination.get("endpoint", ""),
                "DESTINATION_ENV_AWS_ACCESS_KEY_ID": destination.get("accessKeyId", ""),
                "DESTINATION_ENV_AWS_SECRET_ACCESS_KEY": dest_secret or "",
                "DESTINATION_ENV_AWS_BUCKET_NAME": destination.get("bucketName", ""),
            }

        if task.service_type == ServiceType.ENV_RESTORER:
            return {
                "TARGET_NAMESPACE": task.namespace,
                "ENV_BACKUPS_FILENAME_PREFIX": prefix,
                "SOURCE_ENV_AWS_ENDPOINT": source.get("endpoint", ""),
                "SOURCE_ENV_AWS_ACCESS_KEY_ID": source.get("accessKeyId", ""),
                "SOURCE_ENV_AWS_SECRET_ACCESS_KEY": source_secret or "",
                "SOURCE_ENV_AWS_BUCKET_NAME": source.get("bucketName", ""),
            }

        if task.service_type == ServiceType.ENV_SYNCHRONIZER:
            return {
                "SCHEDULE": task.schedule or "",
                "SYNCHRONIZER_ENABLED": "true",
                "ENV_REPOSITORY": config.get("repository", ""),
                "PATH_TO_HELMFILE": config.get("pathToHelmfile", ""),
                "CONFIGMAP_NAME": "",
            }

        return {}

    def _build_manual_restore_job_spec(self, task: Task) -> dict[str, Any]:
        config = self._get_deployment_config(task.service_type, self.settings)
        task_config = task.config or {}
        source = task_config.get("source", {})
        destination = task_config.get("destination", {})
        source_secret = task.secret.source_secret_encrypted if task.secret else None
        dest_secret = task.secret.destination_secret_encrypted if task.secret else None
        prefix = task_config.get("filenamePrefix", "")

        image = self._resolve_image(config)
        resources = {
            "limits": {"cpu": "200m", "memory": "512Mi"},
            "requests": {"cpu": "1m", "memory": "256Mi"},
        }

        if task.service_type == ServiceType.DB_RESTORER:
            env = {
                "DB_BACKUPS_FILENAME_PREFIX": prefix,
                "SOURCE_DB_AWS_ENDPOINT": source.get("endpoint", ""),
                "SOURCE_DB_AWS_ACCESS_KEY_ID": source.get("accessKeyId", ""),
                "SOURCE_DB_AWS_SECRET_ACCESS_KEY": source_secret or "",
                "SOURCE_DB_AWS_BUCKET_NAME": source.get("bucketName", ""),
                "TARGET_DATABASE_HOST": destination.get("host", ""),
                "TARGET_DATABASE_USERNAME": destination.get("username", ""),
                "TARGET_DATABASE_PASSWORD": dest_secret or "",
                "TARGET_DATABASE_NAME": destination.get("name", ""),
            }
            job_env = [{"name": k, "value": v} for k, v in env.items()]
            if dest_secret:
                job_env.append({"name": "PGPASSWORD", "value": dest_secret})
            return {
                "template": {
                    "spec": {
                        "restartPolicy": "OnFailure",
                        "containers": [{
                            "name": task.release_name,
                            "image": image,
                            "imagePullPolicy": config.image_pull_policy,
                            "resources": resources,
                            "env": job_env,
                        }],
                    }
                }
            }

        if task.service_type == ServiceType.S3_RESTORER:
            env = {
                "S3_BACKUPS_FILENAME_PREFIX": prefix,
                "SOURCE_S3_AWS_ENDPOINT": source.get("endpoint", ""),
                "SOURCE_S3_AWS_ACCESS_KEY_ID": source.get("accessKeyId", ""),
                "SOURCE_S3_AWS_SECRET_ACCESS_KEY": source_secret or "",
                "SOURCE_S3_AWS_BUCKET_NAME": source.get("bucketName", ""),
                "TARGET_S3_AWS_ENDPOINT": destination.get("endpoint", ""),
                "TARGET_S3_AWS_ACCESS_KEY_ID": destination.get("accessKeyId", ""),
                "TARGET_S3_AWS_SECRET_ACCESS_KEY": dest_secret or "",
                "TARGET_S3_AWS_BUCKET_NAME": destination.get("bucketName", ""),
                "TARGET_S3_AWS_BUCKET_SUBFOLDER_NAME": destination.get("subfolderName", ""),
            }
            return {
                "template": {
                    "spec": {
                        "restartPolicy": "OnFailure",
                        "containers": [{
                            "name": task.release_name,
                            "image": image,
                            "imagePullPolicy": config.image_pull_policy,
                            "resources": resources,
                            "env": [{"name": k, "value": v} for k, v in env.items()],
                        }],
                    }
                }
            }

        if task.service_type == ServiceType.ENV_RESTORER:
            env = {
                "TARGET_NAMESPACE": task.namespace,
                "ENV_BACKUPS_FILENAME_PREFIX": prefix,
                "SOURCE_ENV_AWS_ENDPOINT": source.get("endpoint", ""),
                "SOURCE_ENV_AWS_ACCESS_KEY_ID": source.get("accessKeyId", ""),
                "SOURCE_ENV_AWS_SECRET_ACCESS_KEY": source_secret or "",
                "SOURCE_ENV_AWS_BUCKET_NAME": source.get("bucketName", ""),
            }
            return {
                "backoffLimit": 0,
                "ttlSecondsAfterFinished": 86400,
                "template": {
                    "spec": {
                        "serviceAccountName": task.release_name,
                        "restartPolicy": "Never",
                        "containers": [{
                            "name": task.release_name,
                            "image": image,
                            "imagePullPolicy": config.image_pull_policy,
                            "resources": resources,
                            "env": [{"name": k, "value": v} for k, v in env.items()],
                        }],
                    }
                },
            }

        raise ValueError("Manual restore jobs are not supported for this task type")

    @staticmethod
    def _resolve_image(config: ServiceDeploymentConfig) -> str:
        if config.image_registry:
            return f"{config.image_registry}/{config.image_repository}:{config.image_tag}"
        return f"{config.image_repository}:{config.image_tag}"

    def _validate_required_secrets(self, task: Task) -> None:
        source_secret = task.secret.source_secret_encrypted if task.secret else None
        dest_secret = task.secret.destination_secret_encrypted if task.secret else None

        if task.service_type == ServiceType.ENV_SYNCHRONIZER:
            return

        if task.service_type == ServiceType.ENV_BACKUPPER:
            if not dest_secret:
                raise HTTPException(status_code=400, detail="Destination AWS secret access key is not configured")
            return

        if task.service_type == ServiceType.ENV_RESTORER:
            if not source_secret:
                raise HTTPException(status_code=400, detail="Source AWS secret access key is not configured")
            return

        if task.service_type == ServiceType.DB_BACKUPPER:
            if not source_secret:
                raise HTTPException(status_code=400, detail="Database password is not configured")
            if not dest_secret:
                raise HTTPException(status_code=400, detail="Destination AWS secret access key is not configured")
            return

        if task.service_type == ServiceType.DB_RESTORER:
            if not dest_secret:
                raise HTTPException(status_code=400, detail="Target database password is not configured")
            if not source_secret:
                raise HTTPException(status_code=400, detail="Source AWS secret access key is not configured")
            return

        if task.service_type == ServiceType.S3_RESTORER:
            if not source_secret:
                raise HTTPException(status_code=400, detail="Source S3 AWS secret access key is not configured")
            if not dest_secret:
                raise HTTPException(status_code=400, detail="Target S3 AWS secret access key is not configured")
            return

        if not source_secret:
            raise HTTPException(status_code=400, detail="Source S3 AWS secret access key is not configured")
        if not dest_secret:
            raise HTTPException(status_code=400, detail="Destination S3 AWS secret access key is not configured")

    def _validate_namespace(self, namespace: str) -> None:
        try:
            if not self.kube.namespace_exists(namespace):
                raise HTTPException(status_code=400, detail=f"Namespace '{namespace}' does not exist")
        except KubernetesError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def _build_release_name(self, task_id: int, service_type: ServiceType) -> str:
        config = self._get_deployment_config(service_type, self.settings)
        return f"{config.release_prefix}-{task_id}"[:53]

    def _record_job_run(self, task: Task, job_name: str, trigger_type: str) -> TaskJobRun:
        now = datetime.now(timezone.utc)
        run = (
            self.db.query(TaskJobRun)
            .filter(TaskJobRun.namespace == task.namespace, TaskJobRun.job_name == job_name)
            .one_or_none()
        )

        if run is None:
            run = TaskJobRun(
                task_id=task.id,
                namespace=task.namespace,
                release_name=task.release_name,
                job_name=job_name,
                trigger_type=trigger_type,
                status="running",
                started_at=now,
                first_seen_at=now,
                last_seen_at=now,
            )
            self.db.add(run)
            self.db.flush()
            return run

        run.task_id = task.id
        run.release_name = task.release_name
        run.trigger_type = trigger_type
        run.status = "running"
        run.started_at = run.started_at or now
        run.last_seen_at = now
        self.db.flush()
        return run

    def create_event_job_run(self, task: Task) -> TaskJobRun:
        if task.trigger_mode != TriggerMode.EVENT_BASED.value or not self._supports_event_mode(task.service_type):
            raise ValueError(
                "Event-based job runs are supported only for db_backupper, s3_backupper, db_restorer, and s3_restorer tasks in event mode"
            )
        return self.create_triggered_job_run(task, trigger_type="event")

    def create_triggered_job_run(self, task: Task, trigger_type: str) -> TaskJobRun:
        if trigger_type not in {"manual", "event"}:
            raise ValueError("Unsupported trigger type")
        if task.trigger_mode != TriggerMode.EVENT_BASED.value or not self._supports_event_mode(task.service_type):
            raise ValueError(
                "Event-mode ad-hoc runs are supported only for db_backupper, s3_backupper, db_restorer, and s3_restorer tasks in event mode"
            )
        if not task.enabled or not task.release_name:
            raise ValueError("Task must be enabled and deployed before ad-hoc runs can start")

        job_name = self.kube.create_job(
            task.namespace,
            task.release_name,
            self._build_ad_hoc_job_spec(task),
            trigger_type=trigger_type,
        )
        run = self._record_job_run(task, job_name, trigger_type)
        task.last_apply_status = "deployed"
        task.last_apply_message = f"{trigger_type.capitalize()} run started: {job_name}"
        task.last_applied_at = datetime.now(timezone.utc)
        self.db.flush()

        if trigger_type == "event":
            self.notifications.notify_event_run_started(task, run)
        else:
            self.notifications.notify_manual_run_started(task, run)

        return run

    def _build_ad_hoc_job_spec(self, task: Task) -> dict[str, Any]:
        config = self._get_deployment_config(task.service_type, self.settings)
        task_config = task.config or {}
        source = task_config.get("source", {})
        destination = task_config.get("destination", {})
        source_secret = task.secret.source_secret_encrypted if task.secret else None
        dest_secret = task.secret.destination_secret_encrypted if task.secret else None
        prefix = task_config.get("filenamePrefix", "")

        image = self._resolve_image(config)
        resources = {
            "limits": {"cpu": "200m", "memory": "512Mi"},
            "requests": {"cpu": "1m", "memory": "256Mi"},
        }

        if task.service_type == ServiceType.DB_BACKUPPER:
            env = {
                "DB_BACKUPS_FILENAME_PREFIX": prefix,
                "DATABASE_HOST": source.get("host", ""),
                "DATABASE_PASSWORD": source_secret or "",
                "DATABASE_USERNAME": source.get("username", ""),
                "DATABASE_NAME": source.get("name", ""),
                "DESTINATION_DB_AWS_ACCESS_KEY_ID": destination.get("accessKeyId", ""),
                "DESTINATION_DB_AWS_SECRET_ACCESS_KEY": dest_secret or "",
                "DESTINATION_DB_AWS_BUCKET_NAME": destination.get("bucketName", ""),
                "DESTINATION_DB_AWS_ENDPOINT": destination.get("endpoint", ""),
            }
            job_env = [{"name": k, "value": v} for k, v in env.items()]
            if source_secret:
                job_env.append({"name": "PGPASSWORD", "value": source_secret})
            return {
                "template": {
                    "spec": {
                        "restartPolicy": "OnFailure",
                        "containers": [{
                            "name": task.release_name,
                            "image": image,
                            "imagePullPolicy": config.image_pull_policy,
                            "resources": resources,
                            "env": job_env,
                        }],
                    }
                }
            }

        if task.service_type == ServiceType.DB_RESTORER:
            env = {
                "DB_BACKUPS_FILENAME_PREFIX": prefix,
                "SOURCE_DB_AWS_ENDPOINT": source.get("endpoint", ""),
                "SOURCE_DB_AWS_ACCESS_KEY_ID": source.get("accessKeyId", ""),
                "SOURCE_DB_AWS_SECRET_ACCESS_KEY": source_secret or "",
                "SOURCE_DB_AWS_BUCKET_NAME": source.get("bucketName", ""),
                "TARGET_DATABASE_HOST": destination.get("host", ""),
                "TARGET_DATABASE_USERNAME": destination.get("username", ""),
                "TARGET_DATABASE_PASSWORD": dest_secret or "",
                "TARGET_DATABASE_NAME": destination.get("name", ""),
            }
            job_env = [{"name": k, "value": v} for k, v in env.items()]
            if dest_secret:
                job_env.append({"name": "PGPASSWORD", "value": dest_secret})
            return {
                "template": {
                    "spec": {
                        "restartPolicy": "OnFailure",
                        "containers": [{
                            "name": task.release_name,
                            "image": image,
                            "imagePullPolicy": config.image_pull_policy,
                            "resources": resources,
                            "env": job_env,
                        }],
                    }
                }
            }

        if task.service_type == ServiceType.S3_BACKUPPER:
            env = {
                "S3_BACKUPS_FILENAME_PREFIX": prefix,
                "SOURCE_S3_AWS_ENDPOINT": source.get("endpoint", ""),
                "SOURCE_S3_AWS_ACCESS_KEY_ID": source.get("accessKeyId", ""),
                "SOURCE_S3_AWS_SECRET_ACCESS_KEY": source_secret or "",
                "SOURCE_S3_AWS_BUCKET_NAME": source.get("bucketName", ""),
                "SOURCE_S3_AWS_BUCKET_SUBFOLDER_NAME": source.get("subfolderName", ""),
                "DESTINATION_S3_AWS_ENDPOINT": destination.get("endpoint", ""),
                "DESTINATION_S3_AWS_ACCESS_KEY_ID": destination.get("accessKeyId", ""),
                "DESTINATION_S3_AWS_SECRET_ACCESS_KEY": dest_secret or "",
                "DESTINATION_S3_AWS_BUCKET_NAME": destination.get("bucketName", ""),
            }
            return {
                "template": {
                    "spec": {
                        "restartPolicy": "OnFailure",
                        "containers": [{
                            "name": task.release_name,
                            "image": image,
                            "imagePullPolicy": config.image_pull_policy,
                            "resources": resources,
                            "env": [{"name": k, "value": v} for k, v in env.items()],
                        }],
                    }
                }
            }

        if task.service_type == ServiceType.S3_RESTORER:
            env = {
                "S3_BACKUPS_FILENAME_PREFIX": prefix,
                "SOURCE_S3_AWS_ENDPOINT": source.get("endpoint", ""),
                "SOURCE_S3_AWS_ACCESS_KEY_ID": source.get("accessKeyId", ""),
                "SOURCE_S3_AWS_SECRET_ACCESS_KEY": source_secret or "",
                "SOURCE_S3_AWS_BUCKET_NAME": source.get("bucketName", ""),
                "TARGET_S3_AWS_ENDPOINT": destination.get("endpoint", ""),
                "TARGET_S3_AWS_ACCESS_KEY_ID": destination.get("accessKeyId", ""),
                "TARGET_S3_AWS_SECRET_ACCESS_KEY": dest_secret or "",
                "TARGET_S3_AWS_BUCKET_NAME": destination.get("bucketName", ""),
                "TARGET_S3_AWS_BUCKET_SUBFOLDER_NAME": destination.get("subfolderName", ""),
            }
            return {
                "template": {
                    "spec": {
                        "restartPolicy": "OnFailure",
                        "containers": [{
                            "name": task.release_name,
                            "image": image,
                            "imagePullPolicy": config.image_pull_policy,
                            "resources": resources,
                            "env": [{"name": k, "value": v} for k, v in env.items()],
                        }],
                    }
                }
            }

        raise ValueError("Ad-hoc jobs are not supported for this task type")

    def _get_task_model(self, task_id: int) -> Task:
        task = (
            self.db.query(Task)
            .options(joinedload(Task.secret), joinedload(Task.event_watch_state))
            .filter(Task.id == task_id)
            .one_or_none()
        )
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.secret is None:
            task.secret = TaskSecret(task=task)
        return task

    def _get_public_task_model(self, task_id: int) -> Task:
        task = self._get_task_model(task_id)
        if task.managed_by_rule_id is not None or task.managed_by_recovery_rule_id is not None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    def _to_summary(self, task: Task) -> TaskSummary:
        common = {
            "id": task.id,
            "name": task.name,
            "namespace": task.namespace,
            "enabled": task.enabled,
            "schedule": self._public_schedule(task),
            "triggerMode": self._public_trigger_mode(task),
            "deployed": task.last_apply_status == "deployed",
            "releaseName": task.release_name,
            "lastApplyStatus": task.last_apply_status,
            "lastApplyMessage": task.last_apply_message,
            "lastAppliedAt": task.last_applied_at,
            "updatedAt": task.updated_at,
        }
        if task.service_type == ServiceType.DB_BACKUPPER:
            return DbTaskSummary(serviceType=task.service_type.value, **common)
        if task.service_type == ServiceType.S3_BACKUPPER:
            return S3TaskSummary(serviceType=task.service_type.value, **common)
        if task.service_type == ServiceType.ENV_BACKUPPER:
            return EnvBackupperTaskSummary(serviceType=task.service_type.value, **common)
        if task.service_type == ServiceType.DB_RESTORER:
            return DbRestorerTaskSummary(serviceType=task.service_type.value, **common)
        if task.service_type == ServiceType.S3_RESTORER:
            return S3RestorerTaskSummary(serviceType=task.service_type.value, **common)
        if task.service_type == ServiceType.ENV_RESTORER:
            return EnvRestorerTaskSummary(serviceType=task.service_type.value, **common)
        if task.service_type == ServiceType.ENV_SYNCHRONIZER:
            return EnvSynchronizerTaskSummary(serviceType=task.service_type.value, **common)
        raise HTTPException(status_code=500, detail="Unsupported public task type")

    def _to_detail(self, task: Task) -> TaskDetail:
        summary = self._to_summary(task)
        config = task.config or {}
        source = config.get("source", {})
        destination = config.get("destination", {})
        source_secret = task.secret.source_secret_encrypted if task.secret else None
        dest_secret = task.secret.destination_secret_encrypted if task.secret else None
        state = task.event_watch_state

        common_detail = {
            "eventWatcherStatus": self._resolve_event_watcher_status(task, state),
            "lastEventDetectedAt": state.last_change_detected_at if state else None,
            "lastEventTriggeredAt": state.last_event_triggered_at if state else None,
            "lastEventMessage": state.last_error_message if state else None,
        }

        if task.service_type == ServiceType.DB_BACKUPPER:
            return DbTaskDetail(
                **summary.model_dump(),
                filenamePrefix=config.get("filenamePrefix", ""),
                sourceHost=source.get("host", ""),
                sourceName=source.get("name", ""),
                sourceUsername=source.get("username", ""),
                destinationEndpoint=destination.get("endpoint", ""),
                destinationBucketName=destination.get("bucketName", ""),
                destinationAccessKeyId=destination.get("accessKeyId", ""),
                hasSourcePassword=bool(source_secret),
                hasDestinationSecret=bool(dest_secret),
                **common_detail,
            )

        if task.service_type == ServiceType.S3_BACKUPPER:
            return S3TaskDetail(
                **summary.model_dump(),
                filenamePrefix=config.get("filenamePrefix", ""),
                sourceEndpoint=source.get("endpoint", ""),
                sourceAccessKeyId=source.get("accessKeyId", ""),
                sourceBucketName=source.get("bucketName", ""),
                sourceSubfolderName=source.get("subfolderName", ""),
                destinationEndpoint=destination.get("endpoint", ""),
                destinationAccessKeyId=destination.get("accessKeyId", ""),
                destinationBucketName=destination.get("bucketName", ""),
                hasSourceSecret=bool(source_secret),
                hasDestinationSecret=bool(dest_secret),
                **common_detail,
            )

        if task.service_type == ServiceType.ENV_BACKUPPER:
            return EnvBackupperTaskDetail(
                **summary.model_dump(),
                filenamePrefix=config.get("filenamePrefix", ""),
                destinationEndpoint=destination.get("endpoint", ""),
                destinationBucketName=destination.get("bucketName", ""),
                destinationAccessKeyId=destination.get("accessKeyId", ""),
                hasDestinationSecret=bool(dest_secret),
            )

        if task.service_type == ServiceType.DB_RESTORER:
            return DbRestorerTaskDetail(
                **summary.model_dump(),
                filenamePrefix=config.get("filenamePrefix", ""),
                sourceEndpoint=source.get("endpoint", ""),
                sourceBucketName=source.get("bucketName", ""),
                sourceAccessKeyId=source.get("accessKeyId", ""),
                destinationHost=destination.get("host", ""),
                destinationName=destination.get("name", ""),
                destinationUsername=destination.get("username", ""),
                hasSourceSecret=bool(source_secret),
                hasDestinationPassword=bool(dest_secret),
            )

        if task.service_type == ServiceType.S3_RESTORER:
            return S3RestorerTaskDetail(
                **summary.model_dump(),
                filenamePrefix=config.get("filenamePrefix", ""),
                sourceEndpoint=source.get("endpoint", ""),
                sourceBucketName=source.get("bucketName", ""),
                sourceAccessKeyId=source.get("accessKeyId", ""),
                destinationEndpoint=destination.get("endpoint", ""),
                destinationBucketName=destination.get("bucketName", ""),
                destinationSubfolderName=destination.get("subfolderName", ""),
                destinationAccessKeyId=destination.get("accessKeyId", ""),
                hasSourceSecret=bool(source_secret),
                hasDestinationSecret=bool(dest_secret),
            )

        if task.service_type == ServiceType.ENV_RESTORER:
            return EnvRestorerTaskDetail(
                **summary.model_dump(),
                filenamePrefix=config.get("filenamePrefix", ""),
                sourceEndpoint=source.get("endpoint", ""),
                sourceBucketName=source.get("bucketName", ""),
                sourceAccessKeyId=source.get("accessKeyId", ""),
                hasSourceSecret=bool(source_secret),
            )

        if task.service_type == ServiceType.ENV_SYNCHRONIZER:
            return EnvSynchronizerTaskDetail(
                **summary.model_dump(),
                repository=config.get("repository", ""),
                pathToHelmfile=config.get("pathToHelmfile", ""),
            )

        raise HTTPException(status_code=500, detail="Unsupported public task type")

    def _resolve_event_watcher_status(self, task: Task, state: TaskEventWatchState | None) -> str:
        if task.trigger_mode != TriggerMode.EVENT_BASED.value:
            return "scheduled"
        if not task.enabled:
            return "disabled"
        if state is None or state.last_polled_at is None:
            return "waiting_for_baseline"
        if state.last_error_at and (state.last_polled_at is None or state.last_error_at >= state.last_polled_at):
            return "error"
        if state.pending_change:
            return "pending"
        cooldown_cutoff = datetime.now(timezone.utc).timestamp() - self.settings.event_watcher_cooldown_seconds
        event_triggered_at = self._normalize_datetime(state.last_event_triggered_at)
        if event_triggered_at and event_triggered_at.timestamp() >= cooldown_cutoff:
            return "cooldown"
        return "watching"

    @staticmethod
    def _public_schedule(task: Task) -> str | None:
        if task.trigger_mode == TriggerMode.MANUAL.value or TaskService._is_public_manual_task_type(task.service_type):
            return None
        if task.trigger_mode == TriggerMode.EVENT_BASED.value and TaskService._supports_event_mode(task.service_type):
            return None
        return task.schedule

    @staticmethod
    def _public_trigger_mode(task: Task) -> str:
        if TaskService._is_public_manual_task_type(task.service_type):
            return TriggerMode.MANUAL.value
        return task.trigger_mode

    @staticmethod
    def _normalize_schedule(task: Task) -> None:
        if task.trigger_mode == TriggerMode.MANUAL.value or TaskService._is_public_manual_task_type(task.service_type):
            task.schedule = None
            return
        if task.trigger_mode == TriggerMode.EVENT_BASED.value and TaskService._supports_event_mode(task.service_type):
            task.schedule = None
            return
        if task.schedule:
            return
        raise HTTPException(status_code=400, detail="Schedule is required for scheduled tasks")

    @staticmethod
    def _validate_trigger_mode(service_type: ServiceType, trigger_mode: str) -> TriggerMode:
        normalized = TriggerMode(trigger_mode)
        if TaskService._is_public_manual_task_type(service_type) and normalized != TriggerMode.MANUAL:
            raise HTTPException(
                status_code=400,
                detail="Manual trigger mode is required for db_restorer, s3_restorer, and env_restorer tasks",
            )
        if normalized == TriggerMode.MANUAL:
            if TaskService._is_public_manual_task_type(service_type):
                return normalized
            raise HTTPException(
                status_code=400,
                detail="Manual trigger mode is supported only for db_restorer, s3_restorer, and env_restorer tasks",
            )
        if normalized == TriggerMode.EVENT_BASED and service_type in {ServiceType.DB_BACKUPPER, ServiceType.S3_BACKUPPER}:
            raise HTTPException(status_code=400, detail="Event-based trigger mode is configured only through event rules")
        if normalized == TriggerMode.EVENT_BASED and not TaskService._supports_event_mode(service_type):
            raise HTTPException(
                status_code=400,
                detail="Event-based trigger mode is supported only for db_backupper, s3_backupper, db_restorer, and s3_restorer tasks",
            )
        return normalized

    @staticmethod
    def _supports_event_mode(service_type: ServiceType) -> bool:
        return service_type in {
            ServiceType.DB_BACKUPPER,
            ServiceType.S3_BACKUPPER,
            ServiceType.DB_RESTORER,
            ServiceType.S3_RESTORER,
        }

    @staticmethod
    def _is_public_manual_task_type(service_type: ServiceType) -> bool:
        return service_type in {
            ServiceType.DB_RESTORER,
            ServiceType.S3_RESTORER,
            ServiceType.ENV_RESTORER,
        }

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)

    def _build_discovered_service(self, service: dict[str, Any]) -> ServiceDiscoveryService:
        name = str(service["name"])
        host = name
        ports = [
            ServiceDiscoveryServicePort(name=port.get("name"), port=int(port["port"]))
            for port in service.get("ports", [])
            if isinstance(port, dict) and isinstance(port.get("port"), int)
        ]
        endpoints = [self._build_discovery_endpoint(host, port) for port in ports]
        return ServiceDiscoveryService(name=name, host=host, ports=ports, endpoints=endpoints)

    @staticmethod
    def _build_discovery_endpoint(host: str, port: ServiceDiscoveryServicePort) -> ServiceDiscoveryEndpoint:
        scheme = TaskService._infer_service_scheme(port)
        if (scheme == "http" and port.port == 80) or (scheme == "https" and port.port == 443):
            value = f"{scheme}://{host}"
        else:
            value = f"{scheme}://{host}:{port.port}"

        label = f"{host}:{port.port}"
        if port.name:
            label = f"{label} ({port.name})"
        return ServiceDiscoveryEndpoint(label=label, value=value)

    @staticmethod
    def _infer_service_scheme(port: ServiceDiscoveryServicePort) -> str:
        port_name = (port.name or "").lower()
        if port.port in {443, 8443} or "https" in port_name or "tls" in port_name:
            return "https"
        return "http"

    @staticmethod
    def _get_deployment_config(service_type: ServiceType, settings: Settings) -> ServiceDeploymentConfig:
        if service_type == ServiceType.DB_BACKUPPER:
            return ServiceDeploymentConfig(
                image_registry=settings.db_backupper_image_registry,
                image_repository=settings.db_backupper_image_repository,
                image_tag=settings.db_backupper_image_tag,
                image_pull_policy=settings.db_backupper_image_pull_policy,
                chart_repository_url=settings.db_backupper_chart_repository_url,
                chart_ref=settings.db_backupper_chart_ref,
                chart_path=settings.db_backupper_chart_path,
                release_prefix="db-backupper",
            )

        if service_type == ServiceType.DB_RESTORER:
            return ServiceDeploymentConfig(
                image_registry=settings.db_restorer_image_registry,
                image_repository=settings.db_restorer_image_repository,
                image_tag=settings.db_restorer_image_tag,
                image_pull_policy=settings.db_restorer_image_pull_policy,
                chart_repository_url=settings.db_restorer_chart_repository_url,
                chart_ref=settings.db_restorer_chart_ref,
                chart_path=settings.db_restorer_chart_path,
                release_prefix="db-restorer",
            )

        if service_type == ServiceType.S3_BACKUPPER:
            return ServiceDeploymentConfig(
                image_registry=settings.s3_backupper_image_registry,
                image_repository=settings.s3_backupper_image_repository,
                image_tag=settings.s3_backupper_image_tag,
                image_pull_policy=settings.s3_backupper_image_pull_policy,
                chart_repository_url=settings.s3_backupper_chart_repository_url,
                chart_ref=settings.s3_backupper_chart_ref,
                chart_path=settings.s3_backupper_chart_path,
                release_prefix="s3-backupper",
            )

        if service_type == ServiceType.S3_RESTORER:
            return ServiceDeploymentConfig(
                image_registry=settings.s3_restorer_image_registry,
                image_repository=settings.s3_restorer_image_repository,
                image_tag=settings.s3_restorer_image_tag,
                image_pull_policy=settings.s3_restorer_image_pull_policy,
                chart_repository_url=settings.s3_restorer_chart_repository_url,
                chart_ref=settings.s3_restorer_chart_ref,
                chart_path=settings.s3_restorer_chart_path,
                release_prefix="s3-restorer",
            )

        if service_type == ServiceType.ENV_BACKUPPER:
            return ServiceDeploymentConfig(
                image_registry=settings.env_backupper_image_registry,
                image_repository=settings.env_backupper_image_repository,
                image_tag=settings.env_backupper_image_tag,
                image_pull_policy=settings.env_backupper_image_pull_policy,
                chart_repository_url=settings.env_backupper_chart_repository_url,
                chart_ref=settings.env_backupper_chart_ref,
                chart_path=settings.env_backupper_chart_path,
                release_prefix="env-backupper",
            )

        if service_type == ServiceType.ENV_RESTORER:
            return ServiceDeploymentConfig(
                image_registry=settings.env_restorer_image_registry,
                image_repository=settings.env_restorer_image_repository,
                image_tag=settings.env_restorer_image_tag,
                image_pull_policy=settings.env_restorer_image_pull_policy,
                chart_repository_url=settings.env_restorer_chart_repository_url,
                chart_ref=settings.env_restorer_chart_ref,
                chart_path=settings.env_restorer_chart_path,
                release_prefix="env-restorer",
            )

        return ServiceDeploymentConfig(
            image_registry=settings.env_synchronizer_image_registry,
            image_repository=settings.env_synchronizer_image_repository,
            image_tag=settings.env_synchronizer_image_tag,
            image_pull_policy=settings.env_synchronizer_image_pull_policy,
            chart_repository_url=settings.env_synchronizer_chart_repository_url,
            chart_ref=settings.env_synchronizer_chart_ref,
            chart_path=settings.env_synchronizer_chart_path,
            release_prefix="env-synchronizer",
        )