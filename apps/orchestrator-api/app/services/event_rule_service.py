from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.helm import HelmError
from app.models.event_rule import BackupEventRule, BackupEventRuleDbConfig, BackupEventRuleS3Config
from app.models.runtime import DataChangeWatchState, RuleJobRun, RuleRunScope, RuleRunType, WatchOwnerType
from app.models.task import ServiceType, TriggerMode
from app.schemas.event_rule import (
    BackupEventRuleComponentDetail,
    BackupEventRuleCreate,
    BackupEventRuleDbConfigDetail,
    BackupEventRuleDbConfigUpdate,
    BackupEventRuleDetail,
    BackupEventRuleS3ConfigDetail,
    BackupEventRuleS3ConfigUpdate,
    BackupEventRuleSummary,
    BackupEventRuleUpdate,
    BackupEventRuleWatcher,
)
from app.services.notification_service import NotificationService
from app.services.task_service import TaskService


class EventRuleService:
    def __init__(
        self,
        db: Session,
        notifications: NotificationService | None = None,
        task_service: TaskService | None = None,
    ) -> None:
        self.db = db
        self.notifications = notifications or NotificationService(db)
        self.task_service = task_service or TaskService(db=db, notifications=self.notifications)

    def list_rules(self) -> list[BackupEventRuleSummary]:
        rules = self.db.query(BackupEventRule).options(*self._rule_load_options()).order_by(BackupEventRule.updated_at.desc()).all()
        return [self._to_summary(rule) for rule in rules]

    def get_rule(self, rule_id: int) -> BackupEventRuleDetail:
        return self._to_detail(self._get_rule_model(rule_id))

    def create_rule(self, payload: BackupEventRuleCreate) -> BackupEventRuleDetail:
        rule = BackupEventRule(name=payload.name, namespace=payload.namespace, enabled=False)
        rule.db_config = BackupEventRuleDbConfig(
            name=payload.dbConfig.name,
            db_backups_filename_prefix=payload.dbConfig.dbBackupsFilenamePrefix,
            database_host=payload.dbConfig.databaseHost,
            database_name=payload.dbConfig.databaseName,
            database_username=payload.dbConfig.databaseUsername,
            database_password_encrypted=payload.dbConfig.databasePassword,
            destination_aws_endpoint=payload.dbConfig.destinationAwsEndpoint,
            destination_aws_bucket_name=payload.dbConfig.destinationAwsBucketName,
            destination_aws_access_key_id=payload.dbConfig.destinationAwsAccessKeyId,
            destination_aws_secret_access_key_encrypted=payload.dbConfig.destinationAwsSecretAccessKey,
        )
        rule.s3_config = BackupEventRuleS3Config(
            name=payload.s3Config.name,
            s3_backups_filename_prefix=payload.s3Config.s3BackupsFilenamePrefix,
            source_s3_aws_endpoint=payload.s3Config.sourceS3AwsEndpoint,
            source_s3_aws_access_key_id=payload.s3Config.sourceS3AwsAccessKeyId,
            source_s3_aws_bucket_name=payload.s3Config.sourceS3AwsBucketName,
            source_s3_aws_bucket_subfolder_name=payload.s3Config.sourceS3AwsBucketSubfolderName or None,
            source_s3_aws_secret_access_key_encrypted=payload.s3Config.sourceS3AwsSecretAccessKey,
            destination_s3_aws_endpoint=payload.s3Config.destinationS3AwsEndpoint,
            destination_s3_aws_access_key_id=payload.s3Config.destinationS3AwsAccessKeyId,
            destination_s3_aws_bucket_name=payload.s3Config.destinationS3AwsBucketName,
            destination_s3_aws_secret_access_key_encrypted=payload.s3Config.destinationS3AwsSecretAccessKey,
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        if payload.enabled:
            return self.enable_rule(rule.id)
        return self._to_detail(self._get_rule_model(rule.id))

    def update_rule(self, rule_id: int, payload: BackupEventRuleUpdate) -> BackupEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        changes = payload.model_dump(exclude_unset=True)
        desired_enabled = changes.pop("enabled", None)

        if "name" in changes:
            rule.name = changes["name"]
        if "namespace" in changes:
            rule.namespace = changes["namespace"]
        if payload.dbConfig is not None:
            self._apply_db_update(rule.db_config, payload.dbConfig)
        if payload.s3Config is not None:
            self._apply_s3_update(rule.s3_config, payload.s3Config)
        self._reset_watch_state(rule.id)
        self.db.commit()

        if desired_enabled is True and not rule.enabled:
            return self.enable_rule(rule.id)
        if desired_enabled is False and rule.enabled:
            return self.disable_rule(rule.id)
        if rule.enabled:
            self._deploy_rule(rule)
        return self._to_detail(self._get_rule_model(rule.id))

    def enable_rule(self, rule_id: int) -> BackupEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        self.task_service._validate_namespace(rule.namespace)
        rule.enabled = True
        self.db.commit()
        self._deploy_rule(rule)
        return self._to_detail(self._get_rule_model(rule.id))

    def disable_rule(self, rule_id: int) -> BackupEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        rule.enabled = False
        self.db.commit()
        self._cleanup_release(rule)
        return self._to_detail(self._get_rule_model(rule.id))

    def run_rule(self, rule_id: int) -> BackupEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        self._start_rule_jobs(rule, trigger_type="manual")
        self.db.commit()
        return self._to_detail(self._get_rule_model(rule.id))

    def delete_rule(self, rule_id: int) -> None:
        rule = self._get_rule_model(rule_id)
        self._cleanup_release(rule)
        state = self._get_watch_state(rule.id)
        if state is not None:
            self.db.delete(state)
        self.db.delete(rule)
        self.db.commit()

    def record_rule_error(self, rule: BackupEventRule, message: str) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_watch_state(rule.id)
        state.last_polled_at = now
        state.last_error_at = now
        state.last_error_message = message
        self.db.flush()
        self.notifications.notify_backup_event_rule_issue(rule, message)

    def record_successful_trigger(self, rule: BackupEventRule, *, trigger_type: str, db_job_name: str, s3_job_name: str) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_watch_state(rule.id)
        state.last_polled_at = state.last_polled_at or now
        state.last_error_at = None
        state.last_error_message = None
        state.last_triggered_at = now
        run = RuleJobRun(
            rule_type=RuleRunType.BACKUP,
            rule_id=rule.id,
            scope=RuleRunScope.BOTH,
            namespace=rule.namespace,
            db_release_name=self._db_release_name(rule.id),
            s3_release_name=self._s3_release_name(rule.id),
            db_job_name=db_job_name,
            s3_job_name=s3_job_name,
            trigger_type=trigger_type,
            status="running",
            started_at=now,
        )
        self.db.add(run)
        self.db.flush()
        self.notifications.notify_backup_event_rule_run_started(rule, trigger_type=trigger_type, db_job_name=db_job_name, s3_job_name=s3_job_name, run=run)

    def _deploy_rule(self, rule: BackupEventRule) -> None:
        self._validate_rule(rule)
        try:
            self.task_service.helm.upgrade_install(
                self._db_release_name(rule.id),
                rule.namespace,
                self.task_service.build_values_for_config(
                    service_type=ServiceType.DB_BACKUPPER,
                    namespace=rule.namespace,
                    trigger_mode=TriggerMode.EVENT_BASED.value,
                    schedule=None,
                    config=rule.db_config,
                ),
                chart_repository_url=self.task_service._get_deployment_config(ServiceType.DB_BACKUPPER, self.task_service.settings).chart_repository_url,
                chart_ref=self.task_service._get_deployment_config(ServiceType.DB_BACKUPPER, self.task_service.settings).chart_ref,
                chart_path=self.task_service._get_deployment_config(ServiceType.DB_BACKUPPER, self.task_service.settings).chart_path,
            )
            self.task_service.helm.upgrade_install(
                self._s3_release_name(rule.id),
                rule.namespace,
                self.task_service.build_values_for_config(
                    service_type=ServiceType.S3_BACKUPPER,
                    namespace=rule.namespace,
                    trigger_mode=TriggerMode.EVENT_BASED.value,
                    schedule=None,
                    config=rule.s3_config,
                ),
                chart_repository_url=self.task_service._get_deployment_config(ServiceType.S3_BACKUPPER, self.task_service.settings).chart_repository_url,
                chart_ref=self.task_service._get_deployment_config(ServiceType.S3_BACKUPPER, self.task_service.settings).chart_ref,
                chart_path=self.task_service._get_deployment_config(ServiceType.S3_BACKUPPER, self.task_service.settings).chart_path,
            )
        except HelmError as exc:
            self.record_rule_error(rule, str(exc))
            self.db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def _cleanup_release(self, rule: BackupEventRule) -> None:
        for release_name in (self._db_release_name(rule.id), self._s3_release_name(rule.id)):
            try:
                self.task_service.helm.uninstall(release_name, rule.namespace)
            except HelmError:
                continue

    def _start_rule_jobs(self, rule: BackupEventRule, *, trigger_type: str) -> None:
        self._validate_rule(rule)
        db_job_name = self.task_service.kube.create_job(
            rule.namespace,
            self._db_release_name(rule.id),
            self.task_service.build_job_spec_for_config(
                service_type=ServiceType.DB_BACKUPPER,
                namespace=rule.namespace,
                schedule=None,
                release_name=self._db_release_name(rule.id),
                config=rule.db_config,
            ),
            trigger_type=trigger_type,
        )
        s3_job_name = self.task_service.kube.create_job(
            rule.namespace,
            self._s3_release_name(rule.id),
            self.task_service.build_job_spec_for_config(
                service_type=ServiceType.S3_BACKUPPER,
                namespace=rule.namespace,
                schedule=None,
                release_name=self._s3_release_name(rule.id),
                config=rule.s3_config,
            ),
            trigger_type=trigger_type,
        )
        self.record_successful_trigger(rule, trigger_type=trigger_type, db_job_name=db_job_name, s3_job_name=s3_job_name)

    def _apply_db_update(self, config: BackupEventRuleDbConfig, payload: BackupEventRuleDbConfigUpdate) -> None:
        self.task_service._apply_fields(
            config,
            payload.model_dump(exclude_unset=True),
            {
                "name": "name",
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

    def _apply_s3_update(self, config: BackupEventRuleS3Config, payload: BackupEventRuleS3ConfigUpdate) -> None:
        self.task_service._apply_fields(
            config,
            payload.model_dump(exclude_unset=True),
            {
                "name": "name",
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

    def _get_rule_model(self, rule_id: int) -> BackupEventRule:
        rule = self.db.query(BackupEventRule).options(*self._rule_load_options()).filter(BackupEventRule.id == rule_id).one_or_none()
        if rule is None:
            raise HTTPException(status_code=404, detail="Backup event rule not found")
        return rule

    @staticmethod
    def _rule_load_options():
        return (joinedload(BackupEventRule.db_config), joinedload(BackupEventRule.s3_config))

    def _validate_rule(self, rule: BackupEventRule) -> None:
        if rule.db_config is None or rule.s3_config is None:
            raise HTTPException(status_code=409, detail="Backup event rule is not fully configured")
        if not rule.db_config.database_password_encrypted:
            raise HTTPException(status_code=400, detail="DB database password is not configured")
        if not rule.db_config.destination_aws_secret_access_key_encrypted:
            raise HTTPException(status_code=400, detail="DB destination AWS secret access key is not configured")
        if not rule.s3_config.source_s3_aws_secret_access_key_encrypted:
            raise HTTPException(status_code=400, detail="S3 source AWS secret access key is not configured")
        if not rule.s3_config.destination_s3_aws_secret_access_key_encrypted:
            raise HTTPException(status_code=400, detail="S3 destination AWS secret access key is not configured")

    def _ensure_watch_state(self, rule_id: int) -> DataChangeWatchState:
        state = self._get_watch_state(rule_id)
        if state is not None:
            return state
        state = DataChangeWatchState(owner_type=WatchOwnerType.BACKUP_RULE, owner_id=rule_id)
        self.db.add(state)
        self.db.flush()
        return state

    def _get_watch_state(self, rule_id: int) -> DataChangeWatchState | None:
        return (
            self.db.query(DataChangeWatchState)
            .filter(DataChangeWatchState.owner_type == WatchOwnerType.BACKUP_RULE, DataChangeWatchState.owner_id == rule_id)
            .one_or_none()
        )

    def _reset_watch_state(self, rule_id: int) -> None:
        state = self._get_watch_state(rule_id)
        if state is not None:
            self.db.delete(state)
            self.db.flush()

    def _resolve_status(self, rule: BackupEventRule, state: DataChangeWatchState | None) -> str:
        if not rule.enabled:
            return "disabled"
        if state is None or state.last_polled_at is None:
            return "waiting_for_baseline"
        if state.last_error_at and state.last_error_at >= state.last_polled_at:
            return "error"
        cooldown_cutoff = datetime.now(timezone.utc).timestamp() - self.task_service.settings.event_watcher_cooldown_seconds
        if state.last_triggered_at and self._normalize_datetime(state.last_triggered_at).timestamp() >= cooldown_cutoff:
            return "cooldown"
        return "watching"

    def _to_summary(self, rule: BackupEventRule) -> BackupEventRuleSummary:
        state = self._get_watch_state(rule.id)
        return BackupEventRuleSummary(
            id=rule.id,
            name=rule.name,
            namespace=rule.namespace,
            enabled=rule.enabled,
            dbConfig=BackupEventRuleComponentDetail(name=rule.db_config.name if rule.db_config else ""),
            s3Config=BackupEventRuleComponentDetail(name=rule.s3_config.name if rule.s3_config else ""),
            watcher=BackupEventRuleWatcher(
                status=self._resolve_status(rule, state),
                lastPolledAt=state.last_polled_at if state else None,
                lastDbChangeAt=state.last_db_change_at if state else None,
                lastS3ChangeAt=state.last_s3_change_at if state else None,
                lastTriggeredAt=state.last_triggered_at if state else None,
                lastErrorAt=state.last_error_at if state else None,
                lastErrorMessage=state.last_error_message if state else None,
            ),
            updatedAt=rule.updated_at,
        )

    def _to_detail(self, rule: BackupEventRule) -> BackupEventRuleDetail:
        summary = self._to_summary(rule)
        if rule.db_config is None or rule.s3_config is None:
            raise HTTPException(status_code=409, detail="Backup event rule is not fully configured")
        return BackupEventRuleDetail(
            **summary.model_dump(),
            dbConfig=BackupEventRuleDbConfigDetail(
                name=rule.db_config.name,
                dbBackupsFilenamePrefix=rule.db_config.db_backups_filename_prefix,
                databaseHost=rule.db_config.database_host,
                databaseName=rule.db_config.database_name,
                databaseUsername=rule.db_config.database_username,
                destinationAwsEndpoint=rule.db_config.destination_aws_endpoint,
                destinationAwsBucketName=rule.db_config.destination_aws_bucket_name,
                destinationAwsAccessKeyId=rule.db_config.destination_aws_access_key_id,
                hasDatabasePassword=bool(rule.db_config.database_password_encrypted),
                hasDestinationAwsSecretAccessKey=bool(rule.db_config.destination_aws_secret_access_key_encrypted),
            ),
            s3Config=BackupEventRuleS3ConfigDetail(
                name=rule.s3_config.name,
                s3BackupsFilenamePrefix=rule.s3_config.s3_backups_filename_prefix,
                sourceS3AwsEndpoint=rule.s3_config.source_s3_aws_endpoint,
                sourceS3AwsAccessKeyId=rule.s3_config.source_s3_aws_access_key_id,
                sourceS3AwsBucketName=rule.s3_config.source_s3_aws_bucket_name,
                sourceS3AwsBucketSubfolderName=rule.s3_config.source_s3_aws_bucket_subfolder_name or "",
                destinationS3AwsEndpoint=rule.s3_config.destination_s3_aws_endpoint,
                destinationS3AwsAccessKeyId=rule.s3_config.destination_s3_aws_access_key_id,
                destinationS3AwsBucketName=rule.s3_config.destination_s3_aws_bucket_name,
                hasSourceS3AwsSecretAccessKey=bool(rule.s3_config.source_s3_aws_secret_access_key_encrypted),
                hasDestinationS3AwsSecretAccessKey=bool(rule.s3_config.destination_s3_aws_secret_access_key_encrypted),
            ),
        )

    @staticmethod
    def _db_release_name(rule_id: int) -> str:
        return f"backup-rule-db-{rule_id}"[:53]

    @staticmethod
    def _s3_release_name(rule_id: int) -> str:
        return f"backup-rule-s3-{rule_id}"[:53]

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)
