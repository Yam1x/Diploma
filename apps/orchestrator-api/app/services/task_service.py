from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.helm import HelmClient, HelmError
from app.core.kube import KubeClient, KubernetesError
from app.core.security import SecretCipher
from app.models.task import ServiceType, Task, TaskSecret
from app.schemas.task import TaskCreate, TaskDetail, TaskSummary, TaskUpdate


class TaskService:
    def __init__(
        self,
        db: Session,
        helm: HelmClient | None = None,
        kube: KubeClient | None = None,
        cipher: SecretCipher | None = None,
    ) -> None:
        self.db = db
        self.helm = helm or HelmClient()
        self.kube = kube or KubeClient()
        self.cipher = cipher or SecretCipher()
        self.settings = get_settings()

    def list_tasks(self) -> list[TaskSummary]:
        tasks = self.db.query(Task).options(joinedload(Task.secret)).order_by(Task.updated_at.desc()).all()
        return [self._to_summary(task) for task in tasks]

    def get_task(self, task_id: int) -> TaskDetail:
        return self._to_detail(self._get_task_model(task_id))

    def create_task(self, payload: TaskCreate) -> TaskDetail:
        task = Task(
            name=payload.name,
            namespace=payload.namespace,
            enabled=False,
            service_type=ServiceType.DB_BACKUPPER,
            schedule=payload.schedule,
            db_backups_filename_prefix=payload.dbBackupsFilenamePrefix,
            database_host=payload.databaseHost,
            database_name=payload.databaseName,
            database_username=payload.databaseUsername,
            destination_aws_endpoint=payload.destinationAwsEndpoint,
            destination_aws_bucket_name=payload.destinationAwsBucketName,
            destination_aws_access_key_id=payload.destinationAwsAccessKeyId,
            release_name="pending",
        )
        task.secret = TaskSecret(
            database_password_encrypted=payload.databasePassword,
            destination_aws_secret_access_key_encrypted=payload.destinationAwsSecretAccessKey,
        )
        self.db.add(task)
        self.db.flush()
        task.release_name = self._build_release_name(task.id)
        self.db.commit()
        self.db.refresh(task)

        if payload.enabled:
            return self.enable_task(task.id)
        return self._to_detail(self._get_task_model(task.id))

    def update_task(self, task_id: int, payload: TaskUpdate) -> TaskDetail:
        task = self._get_task_model(task_id)
        changes = payload.model_dump(exclude_unset=True)
        desired_enabled = changes.pop("enabled", None)
        field_map = {
            "name": "name",
            "namespace": "namespace",
            "schedule": "schedule",
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

        self.db.commit()

        if desired_enabled is True:
            return self.enable_task(task.id)
        if desired_enabled is False and task.enabled:
            return self.disable_task(task.id)
        if task.enabled:
            self._apply_release(task)
        return self._to_detail(self._get_task_model(task.id))

    def enable_task(self, task_id: int) -> TaskDetail:
        task = self._get_task_model(task_id)
        self._validate_namespace(task.namespace)
        task.enabled = True
        self.db.commit()
        self._apply_release(task)
        return self._to_detail(self._get_task_model(task.id))

    def disable_task(self, task_id: int) -> TaskDetail:
        task = self._get_task_model(task_id)
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
        return self._to_detail(task)

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
        return self._to_detail(task)

    def list_namespaces(self) -> list[str]:
        try:
            return self.kube.list_namespaces()
        except KubernetesError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def _apply_release(self, task: Task) -> None:
        self._validate_required_secrets(task)
        values = self._build_values(task)
        try:
            message = self.helm.upgrade_install(task.release_name, task.namespace, values)
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
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def _build_values(self, task: Task) -> dict:
        return {
            "image": {
                "registry": self.settings.backup_image_registry,
                "repository": self.settings.backup_image_repository,
                "tag": self.settings.backup_image_tag,
                "pullPolicy": self.settings.backup_image_pull_policy,
            },
            "resources": {
                "limits": {"cpu": "200m", "memory": "512Mi"},
                "requests": {"cpu": "1m", "memory": "256Mi"},
            },
            "extraConfigMapEnvVars": {
                "BACKUPS_SCHEDULE": task.schedule,
                "DB_BACKUPS_FILENAME_PREFIX": task.db_backups_filename_prefix,
                "DATABASE_HOST": task.database_host,
                "DATABASE_PASSWORD": task.secret.database_password_encrypted or "",
                "DATABASE_USERNAME": task.database_username,
                "DATABASE_NAME": task.database_name,
                "DESTINATION_DB_AWS_ACCESS_KEY_ID": task.destination_aws_access_key_id,
                "DESTINATION_DB_AWS_SECRET_ACCESS_KEY": task.secret.destination_aws_secret_access_key_encrypted or "",
                "DESTINATION_DB_AWS_BUCKET_NAME": task.destination_aws_bucket_name,
                "DESTINATION_DB_AWS_ENDPOINT": task.destination_aws_endpoint,
            },
        }

    def _validate_required_secrets(self, task: Task) -> None:
        if not task.secret.database_password_encrypted:
            raise HTTPException(status_code=400, detail="Database password is not configured")
        if not task.secret.destination_aws_secret_access_key_encrypted:
            raise HTTPException(status_code=400, detail="Destination AWS secret access key is not configured")

    def _validate_namespace(self, namespace: str) -> None:
        try:
            if not self.kube.namespace_exists(namespace):
                raise HTTPException(status_code=400, detail=f"Namespace '{namespace}' does not exist")
        except KubernetesError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def _build_release_name(self, task_id: int) -> str:
        return f"db-backupper-{task_id}"[:53]

    def _get_task_model(self, task_id: int) -> Task:
        task = self.db.query(Task).options(joinedload(Task.secret)).filter(Task.id == task_id).one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.secret is None:
            task.secret = TaskSecret(task=task)
        return task

    def _to_summary(self, task: Task) -> TaskSummary:
        return TaskSummary(
            id=task.id,
            name=task.name,
            namespace=task.namespace,
            enabled=task.enabled,
            serviceType=task.service_type.value,
            schedule=task.schedule,
            deployed=task.last_apply_status == "deployed",
            releaseName=task.release_name,
            lastApplyStatus=task.last_apply_status,
            lastApplyMessage=task.last_apply_message,
            lastAppliedAt=task.last_applied_at,
            updatedAt=task.updated_at,
        )

    def _to_detail(self, task: Task) -> TaskDetail:
        summary = self._to_summary(task)
        return TaskDetail(
            **summary.model_dump(),
            dbBackupsFilenamePrefix=task.db_backups_filename_prefix,
            databaseHost=task.database_host,
            databaseName=task.database_name,
            databaseUsername=task.database_username,
            destinationAwsEndpoint=task.destination_aws_endpoint,
            destinationAwsBucketName=task.destination_aws_bucket_name,
            destinationAwsAccessKeyId=task.destination_aws_access_key_id,
            hasDatabasePassword=bool(task.secret.database_password_encrypted),
            hasDestinationAwsSecretAccessKey=bool(task.secret.destination_aws_secret_access_key_encrypted),
        )
