from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings, get_settings
from app.core.helm import HelmClient, HelmError
from app.core.kube import KubeClient, KubernetesError
from app.models.runtime import DataChangeWatchState, WatchOwnerType
from app.models.task import (
    DbBackupTaskConfig,
    DbRestoreTaskConfig,
    EnvBackupTaskConfig,
    EnvRestoreTaskConfig,
    EnvSyncTaskConfig,
    S3BackupTaskConfig,
    S3RestoreTaskConfig,
    ServiceType,
    Task,
    TaskJobRun,
    TriggerMode,
)
from app.schemas.task import (
    DbBackupTaskConfigDetail,
    DbTaskCreate,
    DbTaskDetail,
    DbTaskUpdate,
    DbRestoreTaskConfigDetail,
    DbRestorerTaskCreate,
    DbRestorerTaskDetail,
    DbRestorerTaskUpdate,
    EnvBackupTaskConfigDetail,
    EnvBackupperTaskCreate,
    EnvBackupperTaskDetail,
    EnvBackupperTaskUpdate,
    EnvRestoreTaskConfigDetail,
    EnvRestorerTaskCreate,
    EnvRestorerTaskDetail,
    EnvRestorerTaskUpdate,
    EnvSyncTaskConfigDetail,
    EnvSynchronizerTaskCreate,
    EnvSynchronizerTaskDetail,
    EnvSynchronizerTaskUpdate,
    EventWatcherState,
    S3BackupTaskConfigDetail,
    S3RestoreTaskConfigDetail,
    S3RestorerTaskCreate,
    S3RestorerTaskDetail,
    S3RestorerTaskUpdate,
    S3TaskCreate,
    S3TaskDetail,
    S3TaskUpdate,
    ServiceDiscoveryEndpoint,
    ServiceDiscoveryResponse,
    ServiceDiscoveryService,
    ServiceDiscoveryServicePort,
    TaskCreate,
    TaskDetail,
    TaskSummary,
    TaskSummaryBase,
    TaskUpdate,
)
from app.services.notification_service import NotificationService


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
        notifications: NotificationService | None = None,
    ) -> None:
        self.db = db
        self.helm = helm or HelmClient()
        self.kube = kube or KubeClient()
        self.notifications = notifications or NotificationService(db)
        self.settings = get_settings()

    def list_tasks(self) -> list[TaskSummary]:
        tasks = self.db.query(Task).options(*self._task_load_options()).order_by(Task.updated_at.desc()).all()
        return [self._to_summary(task) for task in tasks]

    def get_task(self, task_id: int) -> TaskDetail:
        return self._to_detail(self._get_task_model(task_id))

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
        self.db.add(task)
        self.db.flush()
        task.release_name = self._build_release_name(task.id, task.service_type)
        self._create_task_config(task, payload)
        self._normalize_schedule(task)
        self.db.commit()
        self.db.refresh(task)
        if payload.enabled:
            return self.enable_task(task.id)
        return self._to_detail(self._get_task_model(task.id))

    def update_task(self, task_id: int, payload: TaskUpdate) -> TaskDetail:
        task = self._get_task_model(task_id)
        if payload.serviceType != task.service_type.value:
            raise HTTPException(status_code=400, detail="Changing service type is not supported")

        changes = payload.model_dump(exclude_unset=True)
        desired_enabled = changes.pop("enabled", None)
        changes.pop("serviceType", None)
        config_changes = changes.pop("config", None)

        for source, target in {"name": "name", "namespace": "namespace", "schedule": "schedule", "triggerMode": "trigger_mode"}.items():
            if source in changes:
                value = changes[source]
                if source == "triggerMode":
                    value = self._validate_trigger_mode(task.service_type, value).value
                setattr(task, target, value)

        if config_changes:
            self._update_task_config(task, payload)

        self._normalize_schedule(task)
        self.db.commit()
        if desired_enabled is True and not task.enabled:
            return self.enable_task(task.id)
        if desired_enabled is False and task.enabled:
            return self.disable_task(task.id)
        if task.enabled:
            self._apply_release(task)
        return self._to_detail(self._get_task_model(task.id))

    def enable_task(self, task_id: int) -> TaskDetail:
        task = self._get_task_model(task_id)
        self.enable_task_model(task)
        return self._to_detail(self._get_task_model(task.id))

    def disable_task(self, task_id: int) -> TaskDetail:
        task = self._get_task_model(task_id)
        self.disable_task_model(task)
        return self._to_detail(task)

    def run_task(self, task_id: int) -> TaskDetail:
        task = self._get_task_model(task_id)
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
            else:
                job_name = self.kube.create_job_from_cronjob(task.namespace, task.release_name, trigger_type="manual")
                task.last_apply_status = "deployed"
                task.last_apply_message = f"Manual run started: {job_name}"
                task.last_applied_at = datetime.now(timezone.utc)
                run = self._record_job_run(task, job_name, "manual")
                self.db.commit()
                self.notifications.notify_manual_run_started(task, run)
        except KubernetesError as exc:
            task.last_apply_status = "failed"
            task.last_apply_message = str(exc)
            task.last_applied_at = datetime.now(timezone.utc)
            self.db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return self._to_detail(self._get_task_model(task.id))

    def refresh_task(self, task_id: int) -> TaskDetail:
        task = self._get_task_model(task_id)
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
        task = self._get_task_model(task_id)
        self._cleanup_release(task)
        watch_state = self._get_data_watch_state(WatchOwnerType.TASK, task.id)
        if watch_state is not None:
            self.db.delete(watch_state)
        self.db.delete(task)
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
                raise HTTPException(status_code=409, detail=f"Namespace '{namespace}' already exists") from exc
            raise HTTPException(status_code=502, detail=message) from exc

    def list_service_discovery(self, namespace: str) -> ServiceDiscoveryResponse:
        self._validate_namespace(namespace)
        try:
            services = self.kube.list_services(namespace)
        except KubernetesError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return ServiceDiscoveryResponse(services=[self._build_discovered_service(service) for service in services])

    def enable_task_model(self, task: Task) -> None:
        self._validate_namespace(task.namespace)
        task.enabled = True
        self.db.commit()
        self._apply_release(task)

    def disable_task_model(self, task: Task) -> None:
        self._cleanup_release(task)
        task.enabled = False
        task.last_apply_status = "disabled"
        task.last_apply_message = "Release removed"
        task.last_applied_at = datetime.now(timezone.utc)
        self.db.commit()

    def create_event_job_run(self, task: Task) -> TaskJobRun:
        if task.trigger_mode != TriggerMode.EVENT_BASED.value or not self._supports_event_mode(task.service_type):
            raise ValueError("Event-based job runs are supported only for event-capable tasks in event mode")
        return self.create_triggered_job_run(task, trigger_type="event")

    def create_triggered_job_run(self, task: Task, trigger_type: str) -> TaskJobRun:
        if trigger_type not in {"manual", "event"}:
            raise ValueError("Unsupported trigger type")
        if task.trigger_mode != TriggerMode.EVENT_BASED.value or not self._supports_event_mode(task.service_type):
            raise ValueError("Ad-hoc runs are supported only for event-capable tasks in event mode")
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

    def build_values_for_config(
        self,
        *,
        service_type: ServiceType,
        namespace: str,
        trigger_mode: str,
        schedule: str | None,
        config: Any,
    ) -> dict[str, Any]:
        deployment = self._get_deployment_config(service_type, self.settings)
        return self._build_values(service_type, namespace, trigger_mode, schedule, config, deployment)

    def build_job_spec_for_config(
        self,
        *,
        service_type: ServiceType,
        namespace: str,
        schedule: str | None,
        release_name: str,
        config: Any,
    ) -> dict[str, Any]:
        deployment = self._get_deployment_config(service_type, self.settings)
        return self._build_job_spec(service_type, namespace, schedule, release_name, config, deployment)

    def build_manual_restore_job_spec_for_config(
        self,
        *,
        service_type: ServiceType,
        namespace: str,
        release_name: str,
        config: Any,
    ) -> dict[str, Any]:
        if service_type == ServiceType.ENV_RESTORER:
            deployment = self._get_deployment_config(service_type, self.settings)
            runtime = self._build_env_restore_runtime(namespace, config, deployment)
            return {
                "backoffLimit": 0,
                "ttlSecondsAfterFinished": 86400,
                "template": {
                    "spec": {
                        "serviceAccountName": release_name,
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": release_name,
                                "image": runtime["image"],
                                "imagePullPolicy": runtime["imagePullPolicy"],
                                "resources": runtime["resources"],
                                "env": self._build_container_env(runtime["env"]),
                            }
                        ],
                    }
                },
            }
        return self.build_job_spec_for_config(
            service_type=service_type,
            namespace=namespace,
            schedule=None,
            release_name=release_name,
            config=config,
        )

    def _task_load_options(self):
        return (
            joinedload(Task.db_backup_config),
            joinedload(Task.s3_backup_config),
            joinedload(Task.env_backup_config),
            joinedload(Task.db_restore_config),
            joinedload(Task.s3_restore_config),
            joinedload(Task.env_restore_config),
            joinedload(Task.env_sync_config),
        )

    def _get_task_model(self, task_id: int) -> Task:
        task = self.db.query(Task).options(*self._task_load_options()).filter(Task.id == task_id).one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    def _create_task_config(self, task: Task, payload: TaskCreate) -> None:
        if isinstance(payload, DbTaskCreate):
            config = payload.config
            task.db_backup_config = DbBackupTaskConfig(
                db_backups_filename_prefix=config.dbBackupsFilenamePrefix,
                database_host=config.databaseHost,
                database_name=config.databaseName,
                database_username=config.databaseUsername,
                database_password_encrypted=config.databasePassword,
                destination_aws_endpoint=config.destinationAwsEndpoint,
                destination_aws_bucket_name=config.destinationAwsBucketName,
                destination_aws_access_key_id=config.destinationAwsAccessKeyId,
                destination_aws_secret_access_key_encrypted=config.destinationAwsSecretAccessKey,
            )
        elif isinstance(payload, S3TaskCreate):
            config = payload.config
            task.s3_backup_config = S3BackupTaskConfig(
                s3_backups_filename_prefix=config.s3BackupsFilenamePrefix,
                source_s3_aws_endpoint=config.sourceS3AwsEndpoint,
                source_s3_aws_access_key_id=config.sourceS3AwsAccessKeyId,
                source_s3_aws_bucket_name=config.sourceS3AwsBucketName,
                source_s3_aws_bucket_subfolder_name=config.sourceS3AwsBucketSubfolderName or None,
                source_s3_aws_secret_access_key_encrypted=config.sourceS3AwsSecretAccessKey,
                destination_s3_aws_endpoint=config.destinationS3AwsEndpoint,
                destination_s3_aws_access_key_id=config.destinationS3AwsAccessKeyId,
                destination_s3_aws_bucket_name=config.destinationS3AwsBucketName,
                destination_s3_aws_secret_access_key_encrypted=config.destinationS3AwsSecretAccessKey,
            )
        elif isinstance(payload, EnvBackupperTaskCreate):
            config = payload.config
            task.env_backup_config = EnvBackupTaskConfig(
                env_backups_filename_prefix=config.envBackupsFilenamePrefix,
                destination_aws_endpoint=config.destinationAwsEndpoint,
                destination_aws_bucket_name=config.destinationAwsBucketName,
                destination_aws_access_key_id=config.destinationAwsAccessKeyId,
                destination_aws_secret_access_key_encrypted=config.destinationAwsSecretAccessKey,
            )
        elif isinstance(payload, DbRestorerTaskCreate):
            config = payload.config
            task.db_restore_config = DbRestoreTaskConfig(
                db_backups_filename_prefix=config.dbBackupsFilenamePrefix,
                source_aws_endpoint=config.sourceAwsEndpoint,
                source_aws_bucket_name=config.sourceAwsBucketName,
                source_aws_access_key_id=config.sourceAwsAccessKeyId,
                source_aws_secret_access_key_encrypted=config.sourceAwsSecretAccessKey,
                target_database_host=config.targetDatabaseHost,
                target_database_name=config.targetDatabaseName,
                target_database_username=config.targetDatabaseUsername,
                target_database_password_encrypted=config.targetDatabasePassword,
            )
        elif isinstance(payload, S3RestorerTaskCreate):
            config = payload.config
            task.s3_restore_config = S3RestoreTaskConfig(
                s3_backups_filename_prefix=config.s3BackupsFilenamePrefix,
                source_s3_aws_endpoint=config.sourceS3AwsEndpoint,
                source_s3_aws_bucket_name=config.sourceS3AwsBucketName,
                source_s3_aws_access_key_id=config.sourceS3AwsAccessKeyId,
                source_s3_aws_secret_access_key_encrypted=config.sourceS3AwsSecretAccessKey,
                target_s3_aws_endpoint=config.targetS3AwsEndpoint,
                target_s3_aws_bucket_name=config.targetS3AwsBucketName,
                target_s3_aws_bucket_subfolder_name=config.targetS3AwsBucketSubfolderName or None,
                target_s3_aws_access_key_id=config.targetS3AwsAccessKeyId,
                target_s3_aws_secret_access_key_encrypted=config.targetS3AwsSecretAccessKey,
            )
        elif isinstance(payload, EnvRestorerTaskCreate):
            config = payload.config
            task.env_restore_config = EnvRestoreTaskConfig(
                env_backups_filename_prefix=config.envBackupsFilenamePrefix,
                source_aws_endpoint=config.sourceAwsEndpoint,
                source_aws_bucket_name=config.sourceAwsBucketName,
                source_aws_access_key_id=config.sourceAwsAccessKeyId,
                source_aws_secret_access_key_encrypted=config.sourceAwsSecretAccessKey,
            )
        elif isinstance(payload, EnvSynchronizerTaskCreate):
            config = payload.config
            task.env_sync_config = EnvSyncTaskConfig(
                env_repository=config.envRepository,
                path_to_helmfile=config.pathToHelmfile,
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported service type payload")

    def _update_task_config(self, task: Task, payload: TaskUpdate) -> None:
        if isinstance(payload, DbTaskUpdate):
            config = task.db_backup_config
            changes = payload.config.model_dump(exclude_unset=True) if payload.config else {}
            if config is None:
                raise HTTPException(status_code=409, detail="Task config is missing")
            self._apply_fields(
                config,
                changes,
                {
                    "dbBackupsFilenamePrefix": "db_backups_filename_prefix",
                    "databaseHost": "database_host",
                    "databaseName": "database_name",
                    "databaseUsername": "database_username",
                    "databasePassword": "database_password_encrypted",
                    "destinationAwsEndpoint": "destination_aws_endpoint",
                    "destinationAwsBucketName": "destination_aws_bucket_name",
                    "destinationAwsAccessKeyId": "destination_aws_access_key_id",
                    "destinationAwsSecretAccessKey": "destination_aws_secret_access_key_encrypted",
                },
            )
            return
        if isinstance(payload, S3TaskUpdate):
            config = task.s3_backup_config
            changes = payload.config.model_dump(exclude_unset=True) if payload.config else {}
            if config is None:
                raise HTTPException(status_code=409, detail="Task config is missing")
            self._apply_fields(
                config,
                changes,
                {
                    "s3BackupsFilenamePrefix": "s3_backups_filename_prefix",
                    "sourceS3AwsEndpoint": "source_s3_aws_endpoint",
                    "sourceS3AwsAccessKeyId": "source_s3_aws_access_key_id",
                    "sourceS3AwsBucketName": "source_s3_aws_bucket_name",
                    "sourceS3AwsBucketSubfolderName": "source_s3_aws_bucket_subfolder_name",
                    "sourceS3AwsSecretAccessKey": "source_s3_aws_secret_access_key_encrypted",
                    "destinationS3AwsEndpoint": "destination_s3_aws_endpoint",
                    "destinationS3AwsAccessKeyId": "destination_s3_aws_access_key_id",
                    "destinationS3AwsBucketName": "destination_s3_aws_bucket_name",
                    "destinationS3AwsSecretAccessKey": "destination_s3_aws_secret_access_key_encrypted",
                },
            )
            return
        if isinstance(payload, EnvBackupperTaskUpdate):
            config = task.env_backup_config
            changes = payload.config.model_dump(exclude_unset=True) if payload.config else {}
            if config is None:
                raise HTTPException(status_code=409, detail="Task config is missing")
            self._apply_fields(
                config,
                changes,
                {
                    "envBackupsFilenamePrefix": "env_backups_filename_prefix",
                    "destinationAwsEndpoint": "destination_aws_endpoint",
                    "destinationAwsBucketName": "destination_aws_bucket_name",
                    "destinationAwsAccessKeyId": "destination_aws_access_key_id",
                    "destinationAwsSecretAccessKey": "destination_aws_secret_access_key_encrypted",
                },
            )
            return
        if isinstance(payload, DbRestorerTaskUpdate):
            config = task.db_restore_config
            changes = payload.config.model_dump(exclude_unset=True) if payload.config else {}
            if config is None:
                raise HTTPException(status_code=409, detail="Task config is missing")
            self._apply_fields(
                config,
                changes,
                {
                    "dbBackupsFilenamePrefix": "db_backups_filename_prefix",
                    "sourceAwsEndpoint": "source_aws_endpoint",
                    "sourceAwsBucketName": "source_aws_bucket_name",
                    "sourceAwsAccessKeyId": "source_aws_access_key_id",
                    "sourceAwsSecretAccessKey": "source_aws_secret_access_key_encrypted",
                    "targetDatabaseHost": "target_database_host",
                    "targetDatabaseName": "target_database_name",
                    "targetDatabaseUsername": "target_database_username",
                    "targetDatabasePassword": "target_database_password_encrypted",
                },
            )
            return
        if isinstance(payload, S3RestorerTaskUpdate):
            config = task.s3_restore_config
            changes = payload.config.model_dump(exclude_unset=True) if payload.config else {}
            if config is None:
                raise HTTPException(status_code=409, detail="Task config is missing")
            self._apply_fields(
                config,
                changes,
                {
                    "s3BackupsFilenamePrefix": "s3_backups_filename_prefix",
                    "sourceS3AwsEndpoint": "source_s3_aws_endpoint",
                    "sourceS3AwsBucketName": "source_s3_aws_bucket_name",
                    "sourceS3AwsAccessKeyId": "source_s3_aws_access_key_id",
                    "sourceS3AwsSecretAccessKey": "source_s3_aws_secret_access_key_encrypted",
                    "targetS3AwsEndpoint": "target_s3_aws_endpoint",
                    "targetS3AwsBucketName": "target_s3_aws_bucket_name",
                    "targetS3AwsBucketSubfolderName": "target_s3_aws_bucket_subfolder_name",
                    "targetS3AwsAccessKeyId": "target_s3_aws_access_key_id",
                    "targetS3AwsSecretAccessKey": "target_s3_aws_secret_access_key_encrypted",
                },
            )
            return
        if isinstance(payload, EnvRestorerTaskUpdate):
            config = task.env_restore_config
            changes = payload.config.model_dump(exclude_unset=True) if payload.config else {}
            if config is None:
                raise HTTPException(status_code=409, detail="Task config is missing")
            self._apply_fields(
                config,
                changes,
                {
                    "envBackupsFilenamePrefix": "env_backups_filename_prefix",
                    "sourceAwsEndpoint": "source_aws_endpoint",
                    "sourceAwsBucketName": "source_aws_bucket_name",
                    "sourceAwsAccessKeyId": "source_aws_access_key_id",
                    "sourceAwsSecretAccessKey": "source_aws_secret_access_key_encrypted",
                },
            )
            return
        if isinstance(payload, EnvSynchronizerTaskUpdate):
            config = task.env_sync_config
            changes = payload.config.model_dump(exclude_unset=True) if payload.config else {}
            if config is None:
                raise HTTPException(status_code=409, detail="Task config is missing")
            self._apply_fields(config, changes, {"envRepository": "env_repository", "pathToHelmfile": "path_to_helmfile"})
            return
        raise HTTPException(status_code=400, detail="Unsupported service type payload")

    @staticmethod
    def _apply_fields(target: Any, changes: dict[str, Any], mapping: dict[str, str]) -> None:
        for source, destination in mapping.items():
            if source in changes:
                value = changes[source]
                if source.endswith("SubfolderName"):
                    value = value or None
                setattr(target, destination, value)

    def _apply_release(self, task: Task) -> None:
        self._validate_required_secrets(task)
        deployment = self._get_deployment_config(task.service_type, self.settings)
        values = self._build_values(task.service_type, task.namespace, task.trigger_mode, task.schedule, self._task_config(task), deployment)
        try:
            message = self.helm.upgrade_install(
                task.release_name,
                task.namespace,
                values,
                chart_repository_url=deployment.chart_repository_url,
                chart_ref=deployment.chart_ref,
                chart_path=deployment.chart_path,
            )
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

    def _cleanup_release(self, task: Task) -> None:
        if not task.release_name:
            return
        try:
            self.helm.uninstall(task.release_name, task.namespace)
        except HelmError:
            return

    def _build_values(
        self,
        service_type: ServiceType,
        namespace: str,
        trigger_mode: str,
        schedule: str | None,
        config: Any,
        deployment: ServiceDeploymentConfig,
    ) -> dict[str, Any]:
        if service_type == ServiceType.DB_BACKUPPER:
            runtime = self._build_db_runtime(schedule, config, deployment, include_schedule=trigger_mode != TriggerMode.EVENT_BASED.value)
            return self._deployment_values(trigger_mode, runtime, deployment)
        if service_type == ServiceType.S3_BACKUPPER:
            runtime = self._build_s3_runtime(schedule, config, deployment, include_schedule=trigger_mode != TriggerMode.EVENT_BASED.value)
            return self._deployment_values(trigger_mode, runtime, deployment)
        if service_type == ServiceType.ENV_BACKUPPER:
            runtime = self._build_env_backup_runtime(namespace, schedule, config, deployment)
            return self._deployment_values(None, runtime, deployment)
        if service_type == ServiceType.DB_RESTORER:
            runtime = self._build_db_restore_runtime(schedule, config, deployment, include_schedule=trigger_mode != TriggerMode.EVENT_BASED.value)
            return self._deployment_values(trigger_mode, runtime, deployment)
        if service_type == ServiceType.S3_RESTORER:
            runtime = self._build_s3_restore_runtime(schedule, config, deployment, include_schedule=trigger_mode != TriggerMode.EVENT_BASED.value)
            return self._deployment_values(trigger_mode, runtime, deployment)
        if service_type == ServiceType.ENV_RESTORER:
            runtime = self._build_env_restore_runtime(namespace, config, deployment)
            return self._deployment_values(None, runtime, deployment)
        return {
            "image": self._image_values(deployment),
            "resources": {"limits": {"cpu": "200m", "memory": "512Mi"}, "requests": {"cpu": "1m", "memory": "256Mi"}},
            "extraConfigMapEnvVars": {
                "SCHEDULE": schedule or "",
                "SYNCHRONIZER_ENABLED": "true",
                "ENV_REPOSITORY": config.env_repository,
                "PATH_TO_HELMFILE": config.path_to_helmfile,
                "CONFIGMAP_NAME": "",
            },
        }

    def _deployment_values(self, trigger_mode: str | None, runtime: dict[str, Any], deployment: ServiceDeploymentConfig) -> dict[str, Any]:
        values = {
            "image": self._image_values(deployment),
            "resources": runtime["resources"],
            "extraConfigMapEnvVars": runtime["env"],
        }
        if trigger_mode is not None:
            values["triggerMode"] = trigger_mode
        return values

    @staticmethod
    def _image_values(deployment: ServiceDeploymentConfig) -> dict[str, str]:
        return {
            "registry": deployment.image_registry,
            "repository": deployment.image_repository,
            "tag": deployment.image_tag,
            "pullPolicy": deployment.image_pull_policy,
        }

    def _build_db_runtime(self, schedule: str | None, config: DbBackupTaskConfig, deployment: ServiceDeploymentConfig, *, include_schedule: bool) -> dict[str, Any]:
        env = {
            "DB_BACKUPS_FILENAME_PREFIX": config.db_backups_filename_prefix,
            "DATABASE_HOST": config.database_host,
            "DATABASE_PASSWORD": config.database_password_encrypted or "",
            "DATABASE_USERNAME": config.database_username,
            "DATABASE_NAME": config.database_name,
            "DESTINATION_DB_AWS_ACCESS_KEY_ID": config.destination_aws_access_key_id,
            "DESTINATION_DB_AWS_SECRET_ACCESS_KEY": config.destination_aws_secret_access_key_encrypted or "",
            "DESTINATION_DB_AWS_BUCKET_NAME": config.destination_aws_bucket_name,
            "DESTINATION_DB_AWS_ENDPOINT": config.destination_aws_endpoint,
        }
        if include_schedule and schedule:
            env = {"BACKUPS_SCHEDULE": schedule, **env}
        return self._runtime(env, deployment)

    def _build_s3_runtime(self, schedule: str | None, config: S3BackupTaskConfig, deployment: ServiceDeploymentConfig, *, include_schedule: bool) -> dict[str, Any]:
        env = {
            "S3_BACKUPS_FILENAME_PREFIX": config.s3_backups_filename_prefix,
            "SOURCE_S3_AWS_ENDPOINT": config.source_s3_aws_endpoint,
            "SOURCE_S3_AWS_ACCESS_KEY_ID": config.source_s3_aws_access_key_id,
            "SOURCE_S3_AWS_SECRET_ACCESS_KEY": config.source_s3_aws_secret_access_key_encrypted or "",
            "SOURCE_S3_AWS_BUCKET_NAME": config.source_s3_aws_bucket_name,
            "SOURCE_S3_AWS_BUCKET_SUBFOLDER_NAME": config.source_s3_aws_bucket_subfolder_name or "",
            "DESTINATION_S3_AWS_ENDPOINT": config.destination_s3_aws_endpoint,
            "DESTINATION_S3_AWS_ACCESS_KEY_ID": config.destination_s3_aws_access_key_id,
            "DESTINATION_S3_AWS_SECRET_ACCESS_KEY": config.destination_s3_aws_secret_access_key_encrypted or "",
            "DESTINATION_S3_AWS_BUCKET_NAME": config.destination_s3_aws_bucket_name,
        }
        if include_schedule and schedule:
            env = {"BACKUPS_SCHEDULE": schedule, **env}
        return self._runtime(env, deployment)

    def _build_env_backup_runtime(self, namespace: str, schedule: str | None, config: EnvBackupTaskConfig, deployment: ServiceDeploymentConfig) -> dict[str, Any]:
        return self._runtime(
            {
                "BACKUPS_SCHEDULE": schedule or "",
                "TARGET_NAMESPACE": namespace,
                "ENV_BACKUPS_FILENAME_PREFIX": config.env_backups_filename_prefix,
                "DESTINATION_ENV_AWS_ENDPOINT": config.destination_aws_endpoint,
                "DESTINATION_ENV_AWS_ACCESS_KEY_ID": config.destination_aws_access_key_id,
                "DESTINATION_ENV_AWS_SECRET_ACCESS_KEY": config.destination_aws_secret_access_key_encrypted or "",
                "DESTINATION_ENV_AWS_BUCKET_NAME": config.destination_aws_bucket_name,
            },
            deployment,
        )

    def _build_db_restore_runtime(self, schedule: str | None, config: DbRestoreTaskConfig, deployment: ServiceDeploymentConfig, *, include_schedule: bool) -> dict[str, Any]:
        env = {
            "DB_BACKUPS_FILENAME_PREFIX": config.db_backups_filename_prefix,
            "SOURCE_DB_AWS_ENDPOINT": config.source_aws_endpoint,
            "SOURCE_DB_AWS_ACCESS_KEY_ID": config.source_aws_access_key_id,
            "SOURCE_DB_AWS_SECRET_ACCESS_KEY": config.source_aws_secret_access_key_encrypted or "",
            "SOURCE_DB_AWS_BUCKET_NAME": config.source_aws_bucket_name,
            "TARGET_DATABASE_HOST": config.target_database_host,
            "TARGET_DATABASE_USERNAME": config.target_database_username,
            "TARGET_DATABASE_PASSWORD": config.target_database_password_encrypted or "",
            "TARGET_DATABASE_NAME": config.target_database_name,
        }
        if include_schedule and schedule:
            env = {"BACKUPS_SCHEDULE": schedule, **env}
        return self._runtime(env, deployment)

    def _build_s3_restore_runtime(self, schedule: str | None, config: S3RestoreTaskConfig, deployment: ServiceDeploymentConfig, *, include_schedule: bool) -> dict[str, Any]:
        env = {
            "S3_BACKUPS_FILENAME_PREFIX": config.s3_backups_filename_prefix,
            "SOURCE_S3_AWS_ENDPOINT": config.source_s3_aws_endpoint,
            "SOURCE_S3_AWS_ACCESS_KEY_ID": config.source_s3_aws_access_key_id,
            "SOURCE_S3_AWS_SECRET_ACCESS_KEY": config.source_s3_aws_secret_access_key_encrypted or "",
            "SOURCE_S3_AWS_BUCKET_NAME": config.source_s3_aws_bucket_name,
            "TARGET_S3_AWS_ENDPOINT": config.target_s3_aws_endpoint,
            "TARGET_S3_AWS_ACCESS_KEY_ID": config.target_s3_aws_access_key_id,
            "TARGET_S3_AWS_SECRET_ACCESS_KEY": config.target_s3_aws_secret_access_key_encrypted or "",
            "TARGET_S3_AWS_BUCKET_NAME": config.target_s3_aws_bucket_name,
            "TARGET_S3_AWS_BUCKET_SUBFOLDER_NAME": config.target_s3_aws_bucket_subfolder_name or "",
        }
        if include_schedule and schedule:
            env = {"BACKUPS_SCHEDULE": schedule, **env}
        return self._runtime(env, deployment)

    def _build_env_restore_runtime(self, namespace: str, config: EnvRestoreTaskConfig, deployment: ServiceDeploymentConfig) -> dict[str, Any]:
        return self._runtime(
            {
                "TARGET_NAMESPACE": namespace,
                "ENV_BACKUPS_FILENAME_PREFIX": config.env_backups_filename_prefix,
                "SOURCE_ENV_AWS_ENDPOINT": config.source_aws_endpoint,
                "SOURCE_ENV_AWS_ACCESS_KEY_ID": config.source_aws_access_key_id,
                "SOURCE_ENV_AWS_SECRET_ACCESS_KEY": config.source_aws_secret_access_key_encrypted or "",
                "SOURCE_ENV_AWS_BUCKET_NAME": config.source_aws_bucket_name,
            },
            deployment,
        )

    def _runtime(self, env: dict[str, str], deployment: ServiceDeploymentConfig) -> dict[str, Any]:
        return {
            "image": self._resolve_image(deployment),
            "imagePullPolicy": deployment.image_pull_policy,
            "resources": {"limits": {"cpu": "200m", "memory": "512Mi"}, "requests": {"cpu": "1m", "memory": "256Mi"}},
            "env": env,
        }

    def _build_job_spec(
        self,
        service_type: ServiceType,
        namespace: str,
        schedule: str | None,
        release_name: str,
        config: Any,
        deployment: ServiceDeploymentConfig,
    ) -> dict[str, Any]:
        if service_type == ServiceType.DB_BACKUPPER:
            runtime = self._build_db_runtime(schedule, config, deployment, include_schedule=False)
            env = self._build_db_job_env(runtime["env"])
        elif service_type == ServiceType.DB_RESTORER:
            runtime = self._build_db_restore_runtime(schedule, config, deployment, include_schedule=False)
            env = self._build_db_restore_job_env(runtime["env"])
        elif service_type == ServiceType.S3_BACKUPPER:
            runtime = self._build_s3_runtime(schedule, config, deployment, include_schedule=False)
            env = self._build_container_env(runtime["env"])
        elif service_type == ServiceType.S3_RESTORER:
            runtime = self._build_s3_restore_runtime(schedule, config, deployment, include_schedule=False)
            env = self._build_container_env(runtime["env"])
        else:
            raise ValueError("Ad-hoc jobs are not supported for this task type")

        return {
            "template": {
                "spec": {
                    "restartPolicy": "OnFailure",
                    "containers": [
                        {
                            "name": release_name,
                            "image": runtime["image"],
                            "imagePullPolicy": runtime["imagePullPolicy"],
                            "resources": runtime["resources"],
                            "env": env,
                        }
                    ],
                }
            }
        }

    def _build_ad_hoc_job_spec(self, task: Task) -> dict[str, Any]:
        return self.build_job_spec_for_config(
            service_type=task.service_type,
            namespace=task.namespace,
            schedule=task.schedule,
            release_name=task.release_name,
            config=self._task_config(task),
        )

    def _build_manual_restore_job_spec(self, task: Task) -> dict[str, Any]:
        return self.build_manual_restore_job_spec_for_config(
            service_type=task.service_type,
            namespace=task.namespace,
            release_name=task.release_name,
            config=self._task_config(task),
        )

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
        config = self._task_config(task)
        if task.service_type == ServiceType.ENV_SYNCHRONIZER:
            return
        if task.service_type == ServiceType.ENV_BACKUPPER and not config.destination_aws_secret_access_key_encrypted:
            raise HTTPException(status_code=400, detail="Destination AWS secret access key is not configured")
        if task.service_type == ServiceType.ENV_RESTORER and not config.source_aws_secret_access_key_encrypted:
            raise HTTPException(status_code=400, detail="Source AWS secret access key is not configured")
        if task.service_type == ServiceType.DB_BACKUPPER:
            if not config.database_password_encrypted:
                raise HTTPException(status_code=400, detail="Database password is not configured")
            if not config.destination_aws_secret_access_key_encrypted:
                raise HTTPException(status_code=400, detail="Destination AWS secret access key is not configured")
        if task.service_type == ServiceType.DB_RESTORER:
            if not config.target_database_password_encrypted:
                raise HTTPException(status_code=400, detail="Target database password is not configured")
            if not config.source_aws_secret_access_key_encrypted:
                raise HTTPException(status_code=400, detail="Source AWS secret access key is not configured")
        if task.service_type == ServiceType.S3_BACKUPPER:
            if not config.source_s3_aws_secret_access_key_encrypted:
                raise HTTPException(status_code=400, detail="Source S3 AWS secret access key is not configured")
            if not config.destination_s3_aws_secret_access_key_encrypted:
                raise HTTPException(status_code=400, detail="Destination S3 AWS secret access key is not configured")
        if task.service_type == ServiceType.S3_RESTORER:
            if not config.source_s3_aws_secret_access_key_encrypted:
                raise HTTPException(status_code=400, detail="Source S3 AWS secret access key is not configured")
            if not config.target_s3_aws_secret_access_key_encrypted:
                raise HTTPException(status_code=400, detail="Target S3 AWS secret access key is not configured")

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
        run = self.db.query(TaskJobRun).filter(TaskJobRun.namespace == task.namespace, TaskJobRun.job_name == job_name).one_or_none()
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

    def _to_summary(self, task: Task) -> TaskSummary:
        return TaskSummaryBase(
            id=task.id,
            name=task.name,
            namespace=task.namespace,
            enabled=task.enabled,
            serviceType=task.service_type.value,
            schedule=self._public_schedule(task),
            triggerMode=self._public_trigger_mode(task),
            deployed=task.last_apply_status == "deployed",
            releaseName=task.release_name,
            lastApplyStatus=task.last_apply_status,
            lastApplyMessage=task.last_apply_message,
            lastAppliedAt=task.last_applied_at,
            updatedAt=task.updated_at,
        )

    def _to_detail(self, task: Task) -> TaskDetail:
        summary = self._to_summary(task)
        watch_state = self._get_data_watch_state(WatchOwnerType.TASK, task.id)
        watcher = self._to_event_watcher(task, watch_state) if task.service_type in {ServiceType.DB_BACKUPPER, ServiceType.S3_BACKUPPER} else None
        if task.service_type == ServiceType.DB_BACKUPPER:
            config = task.db_backup_config
            return DbTaskDetail(
                **summary.model_dump(),
                config=DbBackupTaskConfigDetail(
                    dbBackupsFilenamePrefix=config.db_backups_filename_prefix,
                    databaseHost=config.database_host,
                    databaseName=config.database_name,
                    databaseUsername=config.database_username,
                    destinationAwsEndpoint=config.destination_aws_endpoint,
                    destinationAwsBucketName=config.destination_aws_bucket_name,
                    destinationAwsAccessKeyId=config.destination_aws_access_key_id,
                    hasDatabasePassword=bool(config.database_password_encrypted),
                    hasDestinationAwsSecretAccessKey=bool(config.destination_aws_secret_access_key_encrypted),
                ),
                watcher=watcher,
            )
        if task.service_type == ServiceType.S3_BACKUPPER:
            config = task.s3_backup_config
            return S3TaskDetail(
                **summary.model_dump(),
                config=S3BackupTaskConfigDetail(
                    s3BackupsFilenamePrefix=config.s3_backups_filename_prefix,
                    sourceS3AwsEndpoint=config.source_s3_aws_endpoint,
                    sourceS3AwsAccessKeyId=config.source_s3_aws_access_key_id,
                    sourceS3AwsBucketName=config.source_s3_aws_bucket_name,
                    sourceS3AwsBucketSubfolderName=config.source_s3_aws_bucket_subfolder_name or "",
                    destinationS3AwsEndpoint=config.destination_s3_aws_endpoint,
                    destinationS3AwsAccessKeyId=config.destination_s3_aws_access_key_id,
                    destinationS3AwsBucketName=config.destination_s3_aws_bucket_name,
                    hasSourceS3AwsSecretAccessKey=bool(config.source_s3_aws_secret_access_key_encrypted),
                    hasDestinationS3AwsSecretAccessKey=bool(config.destination_s3_aws_secret_access_key_encrypted),
                ),
                watcher=watcher,
            )
        if task.service_type == ServiceType.ENV_BACKUPPER:
            config = task.env_backup_config
            return EnvBackupperTaskDetail(
                **summary.model_dump(),
                config=EnvBackupTaskConfigDetail(
                    envBackupsFilenamePrefix=config.env_backups_filename_prefix,
                    destinationAwsEndpoint=config.destination_aws_endpoint,
                    destinationAwsBucketName=config.destination_aws_bucket_name,
                    destinationAwsAccessKeyId=config.destination_aws_access_key_id,
                    hasDestinationAwsSecretAccessKey=bool(config.destination_aws_secret_access_key_encrypted),
                ),
            )
        if task.service_type == ServiceType.DB_RESTORER:
            config = task.db_restore_config
            return DbRestorerTaskDetail(
                **summary.model_dump(),
                config=DbRestoreTaskConfigDetail(
                    dbBackupsFilenamePrefix=config.db_backups_filename_prefix,
                    sourceAwsEndpoint=config.source_aws_endpoint,
                    sourceAwsBucketName=config.source_aws_bucket_name,
                    sourceAwsAccessKeyId=config.source_aws_access_key_id,
                    targetDatabaseHost=config.target_database_host,
                    targetDatabaseName=config.target_database_name,
                    targetDatabaseUsername=config.target_database_username,
                    hasSourceAwsSecretAccessKey=bool(config.source_aws_secret_access_key_encrypted),
                    hasTargetDatabasePassword=bool(config.target_database_password_encrypted),
                ),
            )
        if task.service_type == ServiceType.S3_RESTORER:
            config = task.s3_restore_config
            return S3RestorerTaskDetail(
                **summary.model_dump(),
                config=S3RestoreTaskConfigDetail(
                    s3BackupsFilenamePrefix=config.s3_backups_filename_prefix,
                    sourceS3AwsEndpoint=config.source_s3_aws_endpoint,
                    sourceS3AwsBucketName=config.source_s3_aws_bucket_name,
                    sourceS3AwsAccessKeyId=config.source_s3_aws_access_key_id,
                    targetS3AwsEndpoint=config.target_s3_aws_endpoint,
                    targetS3AwsBucketName=config.target_s3_aws_bucket_name,
                    targetS3AwsBucketSubfolderName=config.target_s3_aws_bucket_subfolder_name or "",
                    targetS3AwsAccessKeyId=config.target_s3_aws_access_key_id,
                    hasSourceS3AwsSecretAccessKey=bool(config.source_s3_aws_secret_access_key_encrypted),
                    hasTargetS3AwsSecretAccessKey=bool(config.target_s3_aws_secret_access_key_encrypted),
                ),
            )
        if task.service_type == ServiceType.ENV_RESTORER:
            config = task.env_restore_config
            return EnvRestorerTaskDetail(
                **summary.model_dump(),
                config=EnvRestoreTaskConfigDetail(
                    envBackupsFilenamePrefix=config.env_backups_filename_prefix,
                    sourceAwsEndpoint=config.source_aws_endpoint,
                    sourceAwsBucketName=config.source_aws_bucket_name,
                    sourceAwsAccessKeyId=config.source_aws_access_key_id,
                    hasSourceAwsSecretAccessKey=bool(config.source_aws_secret_access_key_encrypted),
                ),
            )
        config = task.env_sync_config
        return EnvSynchronizerTaskDetail(
            **summary.model_dump(),
            config=EnvSyncTaskConfigDetail(envRepository=config.env_repository, pathToHelmfile=config.path_to_helmfile),
        )

    def _to_event_watcher(self, task: Task, state: DataChangeWatchState | None) -> EventWatcherState:
        return EventWatcherState(
            status=self._resolve_event_watcher_status(task, state),
            lastDetectedAt=state.last_change_detected_at if state else None,
            lastTriggeredAt=state.last_triggered_at if state else None,
            lastMessage=state.last_error_message if state else None,
        )

    def _resolve_event_watcher_status(self, task: Task, state: DataChangeWatchState | None) -> str:
        if task.trigger_mode != TriggerMode.EVENT_BASED.value:
            return "scheduled"
        if not task.enabled:
            return "disabled"
        if state is None or state.last_polled_at is None:
            return "waiting_for_baseline"
        if state.last_error_at and state.last_error_at >= state.last_polled_at:
            return "error"
        if state.last_change_detected_at and (state.last_triggered_at is None or state.last_change_detected_at > state.last_triggered_at):
            return "pending"
        cooldown_cutoff = datetime.now(timezone.utc).timestamp() - self.settings.event_watcher_cooldown_seconds
        event_triggered_at = self._normalize_datetime(state.last_triggered_at)
        if event_triggered_at and event_triggered_at.timestamp() >= cooldown_cutoff:
            return "cooldown"
        return "watching"

    def _get_data_watch_state(self, owner_type: WatchOwnerType, owner_id: int) -> DataChangeWatchState | None:
        return (
            self.db.query(DataChangeWatchState)
            .filter(DataChangeWatchState.owner_type == owner_type, DataChangeWatchState.owner_id == owner_id)
            .one_or_none()
        )

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
            raise HTTPException(status_code=400, detail="Manual trigger mode is required for db_restorer, s3_restorer, and env_restorer tasks")
        if normalized == TriggerMode.MANUAL and not TaskService._is_public_manual_task_type(service_type):
            raise HTTPException(status_code=400, detail="Manual trigger mode is supported only for restorer tasks")
        if normalized == TriggerMode.EVENT_BASED and not TaskService._supports_event_mode(service_type):
            raise HTTPException(status_code=400, detail="Event-based trigger mode is supported only for db_backupper, s3_backupper, db_restorer, and s3_restorer tasks")
        return normalized

    @staticmethod
    def _supports_event_mode(service_type: ServiceType) -> bool:
        return service_type in {ServiceType.DB_BACKUPPER, ServiceType.S3_BACKUPPER, ServiceType.DB_RESTORER, ServiceType.S3_RESTORER}

    @staticmethod
    def _is_public_manual_task_type(service_type: ServiceType) -> bool:
        return service_type in {ServiceType.DB_RESTORER, ServiceType.S3_RESTORER, ServiceType.ENV_RESTORER}

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)

    def _task_config(self, task: Task) -> Any:
        mapping = {
            ServiceType.DB_BACKUPPER: task.db_backup_config,
            ServiceType.S3_BACKUPPER: task.s3_backup_config,
            ServiceType.ENV_BACKUPPER: task.env_backup_config,
            ServiceType.DB_RESTORER: task.db_restore_config,
            ServiceType.S3_RESTORER: task.s3_restore_config,
            ServiceType.ENV_RESTORER: task.env_restore_config,
            ServiceType.ENV_SYNCHRONIZER: task.env_sync_config,
        }
        config = mapping[task.service_type]
        if config is None:
            raise HTTPException(status_code=409, detail="Task config is missing")
        return config

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
        scheme = "https" if port.port in {443, 8443} or "https" in (port.name or "").lower() or "tls" in (port.name or "").lower() else "http"
        value = f"{scheme}://{host}" if (scheme == "http" and port.port == 80) or (scheme == "https" and port.port == 443) else f"{scheme}://{host}:{port.port}"
        label = f"{host}:{port.port}"
        if port.name:
            label = f"{label} ({port.name})"
        return ServiceDiscoveryEndpoint(label=label, value=value)

    @staticmethod
    def _get_deployment_config(service_type: ServiceType, settings: Settings) -> ServiceDeploymentConfig:
        if service_type == ServiceType.DB_BACKUPPER:
            return ServiceDeploymentConfig(settings.db_backupper_image_registry, settings.db_backupper_image_repository, settings.db_backupper_image_tag, settings.db_backupper_image_pull_policy, settings.db_backupper_chart_repository_url, settings.db_backupper_chart_ref, settings.db_backupper_chart_path, "db-backupper")
        if service_type == ServiceType.DB_RESTORER:
            return ServiceDeploymentConfig(settings.db_restorer_image_registry, settings.db_restorer_image_repository, settings.db_restorer_image_tag, settings.db_restorer_image_pull_policy, settings.db_restorer_chart_repository_url, settings.db_restorer_chart_ref, settings.db_restorer_chart_path, "db-restorer")
        if service_type == ServiceType.S3_BACKUPPER:
            return ServiceDeploymentConfig(settings.s3_backupper_image_registry, settings.s3_backupper_image_repository, settings.s3_backupper_image_tag, settings.s3_backupper_image_pull_policy, settings.s3_backupper_chart_repository_url, settings.s3_backupper_chart_ref, settings.s3_backupper_chart_path, "s3-backupper")
        if service_type == ServiceType.S3_RESTORER:
            return ServiceDeploymentConfig(settings.s3_restorer_image_registry, settings.s3_restorer_image_repository, settings.s3_restorer_image_tag, settings.s3_restorer_image_pull_policy, settings.s3_restorer_chart_repository_url, settings.s3_restorer_chart_ref, settings.s3_restorer_chart_path, "s3-restorer")
        if service_type == ServiceType.ENV_BACKUPPER:
            return ServiceDeploymentConfig(settings.env_backupper_image_registry, settings.env_backupper_image_repository, settings.env_backupper_image_tag, settings.env_backupper_image_pull_policy, settings.env_backupper_chart_repository_url, settings.env_backupper_chart_ref, settings.env_backupper_chart_path, "env-backupper")
        if service_type == ServiceType.ENV_RESTORER:
            return ServiceDeploymentConfig(settings.env_restorer_image_registry, settings.env_restorer_image_repository, settings.env_restorer_image_tag, settings.env_restorer_image_pull_policy, settings.env_restorer_chart_repository_url, settings.env_restorer_chart_ref, settings.env_restorer_chart_path, "env-restorer")
        return ServiceDeploymentConfig(settings.env_synchronizer_image_registry, settings.env_synchronizer_image_repository, settings.env_synchronizer_image_tag, settings.env_synchronizer_image_pull_policy, settings.env_synchronizer_chart_repository_url, settings.env_synchronizer_chart_ref, settings.env_synchronizer_chart_path, "env-synchronizer")
