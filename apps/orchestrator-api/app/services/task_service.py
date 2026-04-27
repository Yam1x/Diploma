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
    DbTaskDetail,
    DbTaskSummary,
    DbTaskUpdate,
    EnvSynchronizerTaskCreate,
    EnvSynchronizerTaskDetail,
    EnvSynchronizerTaskSummary,
    EnvSynchronizerTaskUpdate,
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
        )
        task.secret = TaskSecret()

        if service_type == ServiceType.DB_BACKUPPER:
            db_payload = self._expect_db_create(payload)
            task.db_backups_filename_prefix = db_payload.dbBackupsFilenamePrefix
            task.database_host = db_payload.databaseHost
            task.database_name = db_payload.databaseName
            task.database_username = db_payload.databaseUsername
            task.destination_aws_endpoint = db_payload.destinationAwsEndpoint
            task.destination_aws_bucket_name = db_payload.destinationAwsBucketName
            task.destination_aws_access_key_id = db_payload.destinationAwsAccessKeyId
            task.secret.database_password_encrypted = db_payload.databasePassword
            task.secret.destination_aws_secret_access_key_encrypted = db_payload.destinationAwsSecretAccessKey
        elif service_type == ServiceType.S3_BACKUPPER:
            s3_payload = self._expect_s3_create(payload)
            task.s3_backups_filename_prefix = s3_payload.s3BackupsFilenamePrefix
            task.source_s3_aws_endpoint = s3_payload.sourceS3AwsEndpoint
            task.source_s3_aws_access_key_id = s3_payload.sourceS3AwsAccessKeyId
            task.source_s3_aws_bucket_name = s3_payload.sourceS3AwsBucketName
            task.source_s3_aws_bucket_subfolder_name = s3_payload.sourceS3AwsBucketSubfolderName or None
            task.destination_s3_aws_endpoint = s3_payload.destinationS3AwsEndpoint
            task.destination_s3_aws_access_key_id = s3_payload.destinationS3AwsAccessKeyId
            task.destination_s3_aws_bucket_name = s3_payload.destinationS3AwsBucketName
            task.secret.source_s3_aws_secret_access_key_encrypted = s3_payload.sourceS3AwsSecretAccessKey
            task.secret.destination_s3_aws_secret_access_key_encrypted = s3_payload.destinationS3AwsSecretAccessKey
        else:
            env_payload = self._expect_env_synchronizer_create(payload)
            task.env_repository = env_payload.envRepository
            task.path_to_helmfile = env_payload.pathToHelmfile

        self._normalize_schedule(task)
        self.db.add(task)
        self.db.flush()
        task.release_name = self._build_release_name(task.id, task.service_type)
        self.db.commit()
        self.db.refresh(task)

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

        if task.service_type == ServiceType.DB_BACKUPPER:
            db_changes = self._expect_db_update(payload)
            self._apply_db_update(task, db_changes.model_dump(exclude_unset=True, exclude={"serviceType", "enabled", "name", "namespace", "schedule"}))
        elif task.service_type == ServiceType.S3_BACKUPPER:
            s3_changes = self._expect_s3_update(payload)
            self._apply_s3_update(task, s3_changes.model_dump(exclude_unset=True, exclude={"serviceType", "enabled", "name", "namespace", "schedule"}))
        else:
            env_changes = self._expect_env_synchronizer_update(payload)
            self._apply_env_synchronizer_update(
                task,
                env_changes.model_dump(exclude_unset=True, exclude={"serviceType", "enabled", "name", "namespace", "schedule"}),
            )

        self._normalize_schedule(task)
        self.db.commit()

        if desired_enabled is True:
            return self.enable_task(task.id)
        if desired_enabled is False and task.enabled:
            return self.disable_task(task.id)
        if task.enabled:
            self._apply_release(task)
        return self._to_detail(self._get_task_model(task.id))

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

    def _apply_db_update(self, task: Task, changes: dict) -> None:
        field_map = {
            "dbBackupsFilenamePrefix": "db_backups_filename_prefix",
            "databaseHost": "database_host",
            "databaseName": "database_name",
            "databaseUsername": "database_username",
            "destinationAwsEndpoint": "destination_aws_endpoint",
            "destinationAwsBucketName": "destination_aws_bucket_name",
            "destinationAwsAccessKeyId": "destination_aws_access_key_id",
        }
        for source, target in field_map.items():
            if source in changes:
                setattr(task, target, changes[source])

        if "databasePassword" in changes:
            task.secret.database_password_encrypted = changes["databasePassword"] or None

        if "destinationAwsSecretAccessKey" in changes:
            task.secret.destination_aws_secret_access_key_encrypted = changes["destinationAwsSecretAccessKey"] or None

    def _apply_s3_update(self, task: Task, changes: dict) -> None:
        field_map = {
            "s3BackupsFilenamePrefix": "s3_backups_filename_prefix",
            "sourceS3AwsEndpoint": "source_s3_aws_endpoint",
            "sourceS3AwsAccessKeyId": "source_s3_aws_access_key_id",
            "sourceS3AwsBucketName": "source_s3_aws_bucket_name",
            "sourceS3AwsBucketSubfolderName": "source_s3_aws_bucket_subfolder_name",
            "destinationS3AwsEndpoint": "destination_s3_aws_endpoint",
            "destinationS3AwsAccessKeyId": "destination_s3_aws_access_key_id",
            "destinationS3AwsBucketName": "destination_s3_aws_bucket_name",
        }
        for source, target in field_map.items():
            if source in changes:
                value = changes[source]
                if source == "sourceS3AwsBucketSubfolderName":
                    value = value or None
                setattr(task, target, value)

        if "sourceS3AwsSecretAccessKey" in changes:
            task.secret.source_s3_aws_secret_access_key_encrypted = changes["sourceS3AwsSecretAccessKey"] or None

        if "destinationS3AwsSecretAccessKey" in changes:
            task.secret.destination_s3_aws_secret_access_key_encrypted = changes["destinationS3AwsSecretAccessKey"] or None

    def _apply_env_synchronizer_update(self, task: Task, changes: dict) -> None:
        field_map = {
            "envRepository": "env_repository",
            "pathToHelmfile": "path_to_helmfile",
        }
        for source, target in field_map.items():
            if source in changes:
                setattr(task, target, changes[source])

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
        if task.service_type == ServiceType.DB_BACKUPPER:
            runtime = self._build_db_runtime(task, config, include_schedule=task.trigger_mode != TriggerMode.EVENT_BASED.value)
            return {
                "image": {
                    "registry": config.image_registry,
                    "repository": config.image_repository,
                    "tag": config.image_tag,
                    "pullPolicy": config.image_pull_policy,
                },
                "resources": runtime["resources"],
                "triggerMode": task.trigger_mode,
                "extraConfigMapEnvVars": runtime["env"],
            }

        if task.service_type == ServiceType.DB_RESTORER:
            runtime = self._build_db_restore_runtime(task, config, include_schedule=task.trigger_mode != TriggerMode.EVENT_BASED.value)
            return {
                "image": {
                    "registry": config.image_registry,
                    "repository": config.image_repository,
                    "tag": config.image_tag,
                    "pullPolicy": config.image_pull_policy,
                },
                "resources": runtime["resources"],
                "triggerMode": task.trigger_mode,
                "extraConfigMapEnvVars": runtime["env"],
            }

        if task.service_type == ServiceType.S3_BACKUPPER:
            runtime = self._build_s3_runtime(task, config, include_schedule=task.trigger_mode != TriggerMode.EVENT_BASED.value)
            return {
                "image": {
                    "registry": config.image_registry,
                    "repository": config.image_repository,
                    "tag": config.image_tag,
                    "pullPolicy": config.image_pull_policy,
                },
                "resources": runtime["resources"],
                "triggerMode": task.trigger_mode,
                "extraConfigMapEnvVars": runtime["env"],
            }

        if task.service_type == ServiceType.S3_RESTORER:
            runtime = self._build_s3_restore_runtime(task, config, include_schedule=task.trigger_mode != TriggerMode.EVENT_BASED.value)
            return {
                "image": {
                    "registry": config.image_registry,
                    "repository": config.image_repository,
                    "tag": config.image_tag,
                    "pullPolicy": config.image_pull_policy,
                },
                "resources": runtime["resources"],
                "triggerMode": task.trigger_mode,
                "extraConfigMapEnvVars": runtime["env"],
            }

        return {
            "image": {
                "registry": config.image_registry,
                "repository": config.image_repository,
                "tag": config.image_tag,
                "pullPolicy": config.image_pull_policy,
            },
            "resources": {
                "limits": {"cpu": "200m", "memory": "512Mi"},
                "requests": {"cpu": "1m", "memory": "256Mi"},
            },
            "extraConfigMapEnvVars": self._build_env_vars(task),
        }

    def _build_env_vars(self, task: Task) -> dict[str, str]:
        return {
            "SCHEDULE": task.schedule or "",
            "SYNCHRONIZER_ENABLED": "true",
            "ENV_REPOSITORY": task.env_repository or "",
            "PATH_TO_HELMFILE": task.path_to_helmfile or "",
            "CONFIGMAP_NAME": "",
        }

    def _build_db_runtime(self, task: Task, config: ServiceDeploymentConfig, include_schedule: bool) -> dict[str, Any]:
        env = {
            "DB_BACKUPS_FILENAME_PREFIX": task.db_backups_filename_prefix or "",
            "DATABASE_HOST": task.database_host or "",
            "DATABASE_PASSWORD": task.secret.database_password_encrypted or "",
            "DATABASE_USERNAME": task.database_username or "",
            "DATABASE_NAME": task.database_name or "",
            "DESTINATION_DB_AWS_ACCESS_KEY_ID": task.destination_aws_access_key_id or "",
            "DESTINATION_DB_AWS_SECRET_ACCESS_KEY": task.secret.destination_aws_secret_access_key_encrypted or "",
            "DESTINATION_DB_AWS_BUCKET_NAME": task.destination_aws_bucket_name or "",
            "DESTINATION_DB_AWS_ENDPOINT": task.destination_aws_endpoint or "",
        }
        if include_schedule and task.schedule:
            env = {"BACKUPS_SCHEDULE": task.schedule, **env}

        return {
            "image": self._resolve_image(config),
            "imagePullPolicy": config.image_pull_policy,
            "resources": {
                "limits": {"cpu": "200m", "memory": "512Mi"},
                "requests": {"cpu": "1m", "memory": "256Mi"},
            },
            "env": env,
        }

    def _build_s3_runtime(self, task: Task, config: ServiceDeploymentConfig, include_schedule: bool) -> dict[str, Any]:
        env = {
            "S3_BACKUPS_FILENAME_PREFIX": task.s3_backups_filename_prefix or "",
            "SOURCE_S3_AWS_ENDPOINT": task.source_s3_aws_endpoint or "",
            "SOURCE_S3_AWS_ACCESS_KEY_ID": task.source_s3_aws_access_key_id or "",
            "SOURCE_S3_AWS_SECRET_ACCESS_KEY": task.secret.source_s3_aws_secret_access_key_encrypted or "",
            "SOURCE_S3_AWS_BUCKET_NAME": task.source_s3_aws_bucket_name or "",
            "SOURCE_S3_AWS_BUCKET_SUBFOLDER_NAME": task.source_s3_aws_bucket_subfolder_name or "",
            "DESTINATION_S3_AWS_ENDPOINT": task.destination_s3_aws_endpoint or "",
            "DESTINATION_S3_AWS_ACCESS_KEY_ID": task.destination_s3_aws_access_key_id or "",
            "DESTINATION_S3_AWS_SECRET_ACCESS_KEY": task.secret.destination_s3_aws_secret_access_key_encrypted or "",
            "DESTINATION_S3_AWS_BUCKET_NAME": task.destination_s3_aws_bucket_name or "",
        }
        if include_schedule and task.schedule:
            env = {"BACKUPS_SCHEDULE": task.schedule, **env}

        return {
            "image": self._resolve_image(config),
            "imagePullPolicy": config.image_pull_policy,
            "resources": {
                "limits": {"cpu": "200m", "memory": "512Mi"},
                "requests": {"cpu": "1m", "memory": "256Mi"},
            },
            "env": env,
        }

    def _build_db_restore_runtime(self, task: Task, config: ServiceDeploymentConfig, include_schedule: bool) -> dict[str, Any]:
        env = {
            "DB_BACKUPS_FILENAME_PREFIX": task.db_backups_filename_prefix or "",
            "SOURCE_DB_AWS_ENDPOINT": task.destination_aws_endpoint or "",
            "SOURCE_DB_AWS_ACCESS_KEY_ID": task.destination_aws_access_key_id or "",
            "SOURCE_DB_AWS_SECRET_ACCESS_KEY": task.secret.destination_aws_secret_access_key_encrypted or "",
            "SOURCE_DB_AWS_BUCKET_NAME": task.destination_aws_bucket_name or "",
            "TARGET_DATABASE_HOST": task.database_host or "",
            "TARGET_DATABASE_USERNAME": task.database_username or "",
            "TARGET_DATABASE_PASSWORD": task.secret.database_password_encrypted or "",
            "TARGET_DATABASE_NAME": task.database_name or "",
        }
        if include_schedule and task.schedule:
            env = {"BACKUPS_SCHEDULE": task.schedule, **env}

        return {
            "image": self._resolve_image(config),
            "imagePullPolicy": config.image_pull_policy,
            "resources": {
                "limits": {"cpu": "200m", "memory": "512Mi"},
                "requests": {"cpu": "1m", "memory": "256Mi"},
            },
            "env": env,
        }

    def _build_s3_restore_runtime(self, task: Task, config: ServiceDeploymentConfig, include_schedule: bool) -> dict[str, Any]:
        env = {
            "S3_BACKUPS_FILENAME_PREFIX": task.s3_backups_filename_prefix or "",
            "SOURCE_S3_AWS_ENDPOINT": task.source_s3_aws_endpoint or "",
            "SOURCE_S3_AWS_ACCESS_KEY_ID": task.source_s3_aws_access_key_id or "",
            "SOURCE_S3_AWS_SECRET_ACCESS_KEY": task.secret.source_s3_aws_secret_access_key_encrypted or "",
            "SOURCE_S3_AWS_BUCKET_NAME": task.source_s3_aws_bucket_name or "",
            "TARGET_S3_AWS_ENDPOINT": task.destination_s3_aws_endpoint or "",
            "TARGET_S3_AWS_ACCESS_KEY_ID": task.destination_s3_aws_access_key_id or "",
            "TARGET_S3_AWS_SECRET_ACCESS_KEY": task.secret.destination_s3_aws_secret_access_key_encrypted or "",
            "TARGET_S3_AWS_BUCKET_NAME": task.destination_s3_aws_bucket_name or "",
            "TARGET_S3_AWS_BUCKET_SUBFOLDER_NAME": task.target_s3_aws_bucket_subfolder_name or "",
        }
        if include_schedule and task.schedule:
            env = {"BACKUPS_SCHEDULE": task.schedule, **env}

        return {
            "image": self._resolve_image(config),
            "imagePullPolicy": config.image_pull_policy,
            "resources": {
                "limits": {"cpu": "200m", "memory": "512Mi"},
                "requests": {"cpu": "1m", "memory": "256Mi"},
            },
            "env": env,
        }

    def _build_db_job_spec(self, task: Task, config: ServiceDeploymentConfig) -> dict[str, Any]:
        runtime = self._build_db_runtime(task, config, include_schedule=False)
        return {
            "template": {
                "spec": {
                    "restartPolicy": "OnFailure",
                    "containers": [
                        {
                            "name": task.release_name,
                            "image": runtime["image"],
                            "imagePullPolicy": runtime["imagePullPolicy"],
                            "resources": runtime["resources"],
                            "env": self._build_db_job_env(runtime["env"]),
                        }
                    ],
                }
            }
        }

    def _build_db_restore_job_spec(self, task: Task, config: ServiceDeploymentConfig) -> dict[str, Any]:
        runtime = self._build_db_restore_runtime(task, config, include_schedule=False)
        return {
            "template": {
                "spec": {
                    "restartPolicy": "OnFailure",
                    "containers": [
                        {
                            "name": task.release_name,
                            "image": runtime["image"],
                            "imagePullPolicy": runtime["imagePullPolicy"],
                            "resources": runtime["resources"],
                            "env": self._build_db_restore_job_env(runtime["env"]),
                        }
                    ],
                }
            }
        }

    def _build_s3_job_spec(self, task: Task, config: ServiceDeploymentConfig) -> dict[str, Any]:
        runtime = self._build_s3_runtime(task, config, include_schedule=False)
        return {
            "template": {
                "spec": {
                    "restartPolicy": "OnFailure",
                    "containers": [
                        {
                            "name": task.release_name,
                            "image": runtime["image"],
                            "imagePullPolicy": runtime["imagePullPolicy"],
                            "resources": runtime["resources"],
                            "env": self._build_container_env(runtime["env"]),
                        }
                    ],
                }
            }
        }

    def _build_s3_restore_job_spec(self, task: Task, config: ServiceDeploymentConfig) -> dict[str, Any]:
        runtime = self._build_s3_restore_runtime(task, config, include_schedule=False)
        return {
            "template": {
                "spec": {
                    "restartPolicy": "OnFailure",
                    "containers": [
                        {
                            "name": task.release_name,
                            "image": runtime["image"],
                            "imagePullPolicy": runtime["imagePullPolicy"],
                            "resources": runtime["resources"],
                            "env": self._build_container_env(runtime["env"]),
                        }
                    ],
                }
            }
        }

    def _build_ad_hoc_job_spec(self, task: Task) -> dict[str, Any]:
        config = self._get_deployment_config(task.service_type, self.settings)
        if task.service_type == ServiceType.DB_BACKUPPER:
            return self._build_db_job_spec(task, config)
        if task.service_type == ServiceType.DB_RESTORER:
            return self._build_db_restore_job_spec(task, config)
        if task.service_type == ServiceType.S3_BACKUPPER:
            return self._build_s3_job_spec(task, config)
        if task.service_type == ServiceType.S3_RESTORER:
            return self._build_s3_restore_job_spec(task, config)
        raise ValueError("Ad-hoc jobs are not supported for this task type")

    @staticmethod
    def _resolve_image(config: ServiceDeploymentConfig) -> str:
        if config.image_registry:
            return f"{config.image_registry}/{config.image_repository}:{config.image_tag}"
        return f"{config.image_repository}:{config.image_tag}"

    @staticmethod
    def _build_container_env(env_vars: dict[str, str]) -> list[dict[str, str]]:
        return [{"name": name, "value": value} for name, value in env_vars.items()]

    def _build_db_job_env(self, env_vars: dict[str, str]) -> list[dict[str, str]]:
        job_env = dict(env_vars)
        password = job_env.get("DATABASE_PASSWORD")
        if password is not None:
            job_env["PGPASSWORD"] = password
        return self._build_container_env(job_env)

    def _build_db_restore_job_env(self, env_vars: dict[str, str]) -> list[dict[str, str]]:
        job_env = dict(env_vars)
        password = job_env.get("TARGET_DATABASE_PASSWORD")
        if password is not None:
            job_env["PGPASSWORD"] = password
        return self._build_container_env(job_env)

    def _validate_required_secrets(self, task: Task) -> None:
        if task.service_type == ServiceType.ENV_SYNCHRONIZER:
            return

        if task.service_type == ServiceType.DB_BACKUPPER:
            if not task.secret.database_password_encrypted:
                raise HTTPException(status_code=400, detail="Database password is not configured")
            if not task.secret.destination_aws_secret_access_key_encrypted:
                raise HTTPException(status_code=400, detail="Destination AWS secret access key is not configured")
            return

        if task.service_type == ServiceType.DB_RESTORER:
            if not task.secret.database_password_encrypted:
                raise HTTPException(status_code=400, detail="Target database password is not configured")
            if not task.secret.destination_aws_secret_access_key_encrypted:
                raise HTTPException(status_code=400, detail="Source AWS secret access key is not configured")
            return

        if task.service_type == ServiceType.S3_RESTORER:
            if not task.secret.source_s3_aws_secret_access_key_encrypted:
                raise HTTPException(status_code=400, detail="Source S3 AWS secret access key is not configured")
            if not task.secret.destination_s3_aws_secret_access_key_encrypted:
                raise HTTPException(status_code=400, detail="Target S3 AWS secret access key is not configured")
            return

        if not task.secret.source_s3_aws_secret_access_key_encrypted:
            raise HTTPException(status_code=400, detail="Source S3 AWS secret access key is not configured")
        if not task.secret.destination_s3_aws_secret_access_key_encrypted:
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
            "triggerMode": task.trigger_mode,
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
        if task.service_type == ServiceType.ENV_SYNCHRONIZER:
            return EnvSynchronizerTaskSummary(serviceType=task.service_type.value, **common)
        raise HTTPException(status_code=500, detail="Unsupported public task type")

    def _to_detail(self, task: Task) -> TaskDetail:
        summary = self._to_summary(task)
        if task.service_type == ServiceType.DB_BACKUPPER:
            state = task.event_watch_state
            return DbTaskDetail(
                **summary.model_dump(),
                dbBackupsFilenamePrefix=task.db_backups_filename_prefix or "",
                databaseHost=task.database_host or "",
                databaseName=task.database_name or "",
                databaseUsername=task.database_username or "",
                destinationAwsEndpoint=task.destination_aws_endpoint or "",
                destinationAwsBucketName=task.destination_aws_bucket_name or "",
                destinationAwsAccessKeyId=task.destination_aws_access_key_id or "",
                hasDatabasePassword=bool(task.secret.database_password_encrypted),
                hasDestinationAwsSecretAccessKey=bool(task.secret.destination_aws_secret_access_key_encrypted),
                eventWatcherStatus=self._resolve_event_watcher_status(task, state),
                lastEventDetectedAt=state.last_change_detected_at if state else None,
                lastEventTriggeredAt=state.last_event_triggered_at if state else None,
                lastEventMessage=state.last_error_message if state else None,
            )

        if task.service_type == ServiceType.S3_BACKUPPER:
            state = task.event_watch_state
            return S3TaskDetail(
                **summary.model_dump(),
                s3BackupsFilenamePrefix=task.s3_backups_filename_prefix or "",
                sourceS3AwsEndpoint=task.source_s3_aws_endpoint or "",
                sourceS3AwsAccessKeyId=task.source_s3_aws_access_key_id or "",
                sourceS3AwsBucketName=task.source_s3_aws_bucket_name or "",
                sourceS3AwsBucketSubfolderName=task.source_s3_aws_bucket_subfolder_name or "",
                destinationS3AwsEndpoint=task.destination_s3_aws_endpoint or "",
                destinationS3AwsAccessKeyId=task.destination_s3_aws_access_key_id or "",
                destinationS3AwsBucketName=task.destination_s3_aws_bucket_name or "",
                hasSourceS3AwsSecretAccessKey=bool(task.secret.source_s3_aws_secret_access_key_encrypted),
                hasDestinationS3AwsSecretAccessKey=bool(task.secret.destination_s3_aws_secret_access_key_encrypted),
                eventWatcherStatus=self._resolve_event_watcher_status(task, state),
                lastEventDetectedAt=state.last_change_detected_at if state else None,
                lastEventTriggeredAt=state.last_event_triggered_at if state else None,
                lastEventMessage=state.last_error_message if state else None,
            )

        if task.service_type == ServiceType.ENV_SYNCHRONIZER:
            return EnvSynchronizerTaskDetail(
                **summary.model_dump(),
                envRepository=task.env_repository or "",
                pathToHelmfile=task.path_to_helmfile or "",
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
        if task.trigger_mode == TriggerMode.EVENT_BASED.value and TaskService._supports_event_mode(task.service_type):
            return None
        return task.schedule

    @staticmethod
    def _normalize_schedule(task: Task) -> None:
        if task.trigger_mode == TriggerMode.EVENT_BASED.value and TaskService._supports_event_mode(task.service_type):
            task.schedule = None
            return
        if task.schedule:
            return
        raise HTTPException(status_code=400, detail="Schedule is required for scheduled tasks")

    @staticmethod
    def _validate_trigger_mode(service_type: ServiceType, trigger_mode: str) -> TriggerMode:
        normalized = TriggerMode(trigger_mode)
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
    def _expect_db_create(payload: TaskCreate) -> DbTaskCreate:
        if not isinstance(payload, DbTaskCreate):
            raise HTTPException(status_code=400, detail="Unsupported service type payload")
        return payload

    @staticmethod
    def _expect_s3_create(payload: TaskCreate) -> S3TaskCreate:
        if not isinstance(payload, S3TaskCreate):
            raise HTTPException(status_code=400, detail="Unsupported service type payload")
        return payload

    @staticmethod
    def _expect_env_synchronizer_create(payload: TaskCreate) -> EnvSynchronizerTaskCreate:
        if not isinstance(payload, EnvSynchronizerTaskCreate):
            raise HTTPException(status_code=400, detail="Unsupported service type payload")
        return payload

    @staticmethod
    def _expect_db_update(payload: TaskUpdate) -> DbTaskUpdate:
        if not isinstance(payload, DbTaskUpdate):
            raise HTTPException(status_code=400, detail="Unsupported service type payload")
        return payload

    @staticmethod
    def _expect_s3_update(payload: TaskUpdate) -> S3TaskUpdate:
        if not isinstance(payload, S3TaskUpdate):
            raise HTTPException(status_code=400, detail="Unsupported service type payload")
        return payload

    @staticmethod
    def _expect_env_synchronizer_update(payload: TaskUpdate) -> EnvSynchronizerTaskUpdate:
        if not isinstance(payload, EnvSynchronizerTaskUpdate):
            raise HTTPException(status_code=400, detail="Unsupported service type payload")
        return payload

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
