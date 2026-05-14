from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.helm import HelmError
from app.models.recovery_rule import RecoveryEventRule, RecoveryEventRuleDbConfig, RecoveryEventRuleS3Config
from app.models.runtime import EmptyStateWatchState, RuleJobRun, RuleRunScope, RuleRunType, WatchOwnerType
from app.models.task import ServiceType
from app.schemas.recovery_rule import (
    RecoveryEventRuleComponentDetail,
    RecoveryEventRuleCreate,
    RecoveryEventRuleDbConfigDetail,
    RecoveryEventRuleDbConfigUpdate,
    RecoveryEventRuleDetail,
    RecoveryEventRuleS3ConfigDetail,
    RecoveryEventRuleS3ConfigUpdate,
    RecoveryEventRuleSummary,
    RecoveryEventRuleUpdate,
    RecoveryEventRuleWatcher,
)
from app.services.notification_service import NotificationService
from app.services.task_service import TaskService


class RecoveryEventRuleService:
    def __init__(
        self,
        db: Session,
        notifications: NotificationService | None = None,
        task_service: TaskService | None = None,
    ) -> None:
        self.db = db
        self.notifications = notifications or NotificationService(db)
        self.task_service = task_service or TaskService(db=db, notifications=self.notifications)

    def list_rules(self) -> list[RecoveryEventRuleSummary]:
        rules = self.db.query(RecoveryEventRule).options(*self._rule_load_options()).order_by(RecoveryEventRule.updated_at.desc()).all()
        return [self._to_summary(rule) for rule in rules]

    def get_rule(self, rule_id: int) -> RecoveryEventRuleDetail:
        return self._to_detail(self._get_rule_model(rule_id))

    def create_rule(self, payload: RecoveryEventRuleCreate) -> RecoveryEventRuleDetail:
        rule = RecoveryEventRule(name=payload.name, namespace=payload.namespace, enabled=False)
        rule.db_config = RecoveryEventRuleDbConfig(
            name=payload.dbConfig.name,
            db_backups_filename_prefix=payload.dbConfig.dbBackupsFilenamePrefix,
            source_aws_endpoint=payload.dbConfig.sourceAwsEndpoint,
            source_aws_bucket_name=payload.dbConfig.sourceAwsBucketName,
            source_aws_access_key_id=payload.dbConfig.sourceAwsAccessKeyId,
            source_aws_secret_access_key_encrypted=payload.dbConfig.sourceAwsSecretAccessKey,
            target_database_host=payload.dbConfig.targetDatabaseHost,
            target_database_name=payload.dbConfig.targetDatabaseName,
            target_database_username=payload.dbConfig.targetDatabaseUsername,
            target_database_password_encrypted=payload.dbConfig.targetDatabasePassword,
        )
        rule.s3_config = RecoveryEventRuleS3Config(
            name=payload.s3Config.name,
            s3_backups_filename_prefix=payload.s3Config.s3BackupsFilenamePrefix,
            source_s3_aws_endpoint=payload.s3Config.sourceS3AwsEndpoint,
            source_s3_aws_bucket_name=payload.s3Config.sourceS3AwsBucketName,
            source_s3_aws_access_key_id=payload.s3Config.sourceS3AwsAccessKeyId,
            source_s3_aws_secret_access_key_encrypted=payload.s3Config.sourceS3AwsSecretAccessKey,
            target_s3_aws_endpoint=payload.s3Config.targetS3AwsEndpoint,
            target_s3_aws_bucket_name=payload.s3Config.targetS3AwsBucketName,
            target_s3_aws_bucket_subfolder_name=payload.s3Config.targetS3AwsBucketSubfolderName or None,
            target_s3_aws_access_key_id=payload.s3Config.targetS3AwsAccessKeyId,
            target_s3_aws_secret_access_key_encrypted=payload.s3Config.targetS3AwsSecretAccessKey,
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        if payload.enabled:
            return self.enable_rule(rule.id)
        return self._to_detail(self._get_rule_model(rule.id))

    def update_rule(self, rule_id: int, payload: RecoveryEventRuleUpdate) -> RecoveryEventRuleDetail:
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

    def enable_rule(self, rule_id: int) -> RecoveryEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        self.task_service._validate_namespace(rule.namespace)
        rule.enabled = True
        self.db.commit()
        self._deploy_rule(rule)
        return self._to_detail(self._get_rule_model(rule.id))

    def disable_rule(self, rule_id: int) -> RecoveryEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        rule.enabled = False
        self.db.commit()
        self._cleanup_release(rule)
        return self._to_detail(self._get_rule_model(rule.id))

    def run_rule(self, rule_id: int) -> RecoveryEventRuleDetail:
        return self._run_rule(rule_id, run_db=True, run_s3=True)

    def run_rule_db(self, rule_id: int) -> RecoveryEventRuleDetail:
        return self._run_rule(rule_id, run_db=True, run_s3=False)

    def run_rule_s3(self, rule_id: int) -> RecoveryEventRuleDetail:
        return self._run_rule(rule_id, run_db=False, run_s3=True)

    def delete_rule(self, rule_id: int) -> None:
        rule = self._get_rule_model(rule_id)
        self._cleanup_release(rule)
        state = self._get_watch_state(rule.id)
        if state is not None:
            self.db.delete(state)
        self.db.delete(rule)
        self.db.commit()

    def record_rule_error(self, rule: RecoveryEventRule, message: str) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_watch_state(rule.id)
        state.last_polled_at = now
        state.last_error_at = now
        state.last_error_message = message
        self.db.flush()
        self.notifications.notify_recovery_event_rule_issue(rule, message)

    def record_successful_trigger(
        self,
        rule: RecoveryEventRule,
        *,
        trigger_type: str,
        db_job_name: str | None = None,
        s3_job_name: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_watch_state(rule.id)
        state.last_polled_at = state.last_polled_at or now
        state.last_error_at = None
        state.last_error_message = None
        if db_job_name:
            state.last_db_triggered_at = now
        if s3_job_name:
            state.last_s3_triggered_at = now
        run = RuleJobRun(
            rule_type=RuleRunType.RECOVERY,
            rule_id=rule.id,
            scope=RuleRunScope.BOTH if db_job_name and s3_job_name else RuleRunScope.DB if db_job_name else RuleRunScope.S3,
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
        self.notifications.notify_recovery_event_rule_run_started(rule, trigger_type=trigger_type, db_job_name=db_job_name, s3_job_name=s3_job_name, run=run)

    def _deploy_rule(self, rule: RecoveryEventRule) -> None:
        self._validate_rule(rule)
        try:
            self.task_service.helm.upgrade_install(
                self._db_release_name(rule.id),
                rule.namespace,
                self.task_service.build_values_for_config(
                    service_type=ServiceType.DB_RESTORER,
                    namespace=rule.namespace,
                    trigger_mode="event_based",
                    schedule=None,
                    config=rule.db_config,
                ),
                chart_repository_url=self.task_service._get_deployment_config(ServiceType.DB_RESTORER, self.task_service.settings).chart_repository_url,
                chart_ref=self.task_service._get_deployment_config(ServiceType.DB_RESTORER, self.task_service.settings).chart_ref,
                chart_path=self.task_service._get_deployment_config(ServiceType.DB_RESTORER, self.task_service.settings).chart_path,
            )
            self.task_service.helm.upgrade_install(
                self._s3_release_name(rule.id),
                rule.namespace,
                self.task_service.build_values_for_config(
                    service_type=ServiceType.S3_RESTORER,
                    namespace=rule.namespace,
                    trigger_mode="event_based",
                    schedule=None,
                    config=rule.s3_config,
                ),
                chart_repository_url=self.task_service._get_deployment_config(ServiceType.S3_RESTORER, self.task_service.settings).chart_repository_url,
                chart_ref=self.task_service._get_deployment_config(ServiceType.S3_RESTORER, self.task_service.settings).chart_ref,
                chart_path=self.task_service._get_deployment_config(ServiceType.S3_RESTORER, self.task_service.settings).chart_path,
            )
        except HelmError as exc:
            self.record_rule_error(rule, str(exc))
            self.db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def _cleanup_release(self, rule: RecoveryEventRule) -> None:
        for release_name in (self._db_release_name(rule.id), self._s3_release_name(rule.id)):
            try:
                self.task_service.helm.uninstall(release_name, rule.namespace)
            except HelmError:
                continue

    def _start_rule_jobs(self, rule: RecoveryEventRule, *, trigger_type: str, run_db: bool, run_s3: bool) -> None:
        self._validate_rule(rule)
        db_job_name = None
        s3_job_name = None
        if run_db:
            db_job_name = self.task_service.kube.create_job(
                rule.namespace,
                self._db_release_name(rule.id),
                self.task_service.build_job_spec_for_config(
                    service_type=ServiceType.DB_RESTORER,
                    namespace=rule.namespace,
                    schedule=None,
                    release_name=self._db_release_name(rule.id),
                    config=rule.db_config,
                ),
                trigger_type=trigger_type,
            )
        if run_s3:
            s3_job_name = self.task_service.kube.create_job(
                rule.namespace,
                self._s3_release_name(rule.id),
                self.task_service.build_job_spec_for_config(
                    service_type=ServiceType.S3_RESTORER,
                    namespace=rule.namespace,
                    schedule=None,
                    release_name=self._s3_release_name(rule.id),
                    config=rule.s3_config,
                ),
                trigger_type=trigger_type,
            )
        self.record_successful_trigger(rule, trigger_type=trigger_type, db_job_name=db_job_name, s3_job_name=s3_job_name)

    def _run_rule(self, rule_id: int, *, run_db: bool, run_s3: bool) -> RecoveryEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        self._start_rule_jobs(rule, trigger_type="manual", run_db=run_db, run_s3=run_s3)
        self.db.commit()
        return self._to_detail(self._get_rule_model(rule.id))

    def _apply_db_update(self, config: RecoveryEventRuleDbConfig, payload: RecoveryEventRuleDbConfigUpdate) -> None:
        self.task_service._apply_fields(
            config,
            payload.model_dump(exclude_unset=True),
            {
                "name": "name",
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

    def _apply_s3_update(self, config: RecoveryEventRuleS3Config, payload: RecoveryEventRuleS3ConfigUpdate) -> None:
        self.task_service._apply_fields(
            config,
            payload.model_dump(exclude_unset=True),
            {
                "name": "name",
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

    def _get_rule_model(self, rule_id: int) -> RecoveryEventRule:
        rule = self.db.query(RecoveryEventRule).options(*self._rule_load_options()).filter(RecoveryEventRule.id == rule_id).one_or_none()
        if rule is None:
            raise HTTPException(status_code=404, detail="Recovery event rule not found")
        return rule

    @staticmethod
    def _rule_load_options():
        return (joinedload(RecoveryEventRule.db_config), joinedload(RecoveryEventRule.s3_config))

    def _validate_rule(self, rule: RecoveryEventRule) -> None:
        if rule.db_config is None or rule.s3_config is None:
            raise HTTPException(status_code=409, detail="Recovery event rule is not fully configured")
        if not rule.db_config.source_aws_secret_access_key_encrypted:
            raise HTTPException(status_code=400, detail="DB source AWS secret access key is not configured")
        if not rule.db_config.target_database_password_encrypted:
            raise HTTPException(status_code=400, detail="DB target database password is not configured")
        if not rule.s3_config.source_s3_aws_secret_access_key_encrypted:
            raise HTTPException(status_code=400, detail="S3 source AWS secret access key is not configured")
        if not rule.s3_config.target_s3_aws_secret_access_key_encrypted:
            raise HTTPException(status_code=400, detail="S3 target AWS secret access key is not configured")

    def _ensure_watch_state(self, rule_id: int) -> EmptyStateWatchState:
        state = self._get_watch_state(rule_id)
        if state is not None:
            return state
        state = EmptyStateWatchState(owner_type=WatchOwnerType.RECOVERY_RULE, owner_id=rule_id)
        self.db.add(state)
        self.db.flush()
        return state

    def _get_watch_state(self, rule_id: int) -> EmptyStateWatchState | None:
        return (
            self.db.query(EmptyStateWatchState)
            .filter(EmptyStateWatchState.owner_type == WatchOwnerType.RECOVERY_RULE, EmptyStateWatchState.owner_id == rule_id)
            .one_or_none()
        )

    def _reset_watch_state(self, rule_id: int) -> None:
        state = self._get_watch_state(rule_id)
        if state is not None:
            self.db.delete(state)
            self.db.flush()

    def _resolve_status(self, rule: RecoveryEventRule, state: EmptyStateWatchState | None) -> str:
        if not rule.enabled:
            return "disabled"
        if self._has_running_runs(rule.id):
            return "restoring"
        if state is None or state.last_polled_at is None:
            return "waiting_for_baseline"
        if state.last_error_at and state.last_error_at >= state.last_polled_at:
            return "error"
        cooldown_cutoff = datetime.now(timezone.utc).timestamp() - self.task_service.settings.event_watcher_cooldown_seconds
        if (
            state.last_db_triggered_at and self._normalize_datetime(state.last_db_triggered_at).timestamp() >= cooldown_cutoff
        ) or (
            state.last_s3_triggered_at and self._normalize_datetime(state.last_s3_triggered_at).timestamp() >= cooldown_cutoff
        ):
            return "cooldown"
        return "watching"

    def _has_running_runs(self, rule_id: int) -> bool:
        return (
            self.db.query(RuleJobRun)
            .filter(RuleJobRun.rule_type == RuleRunType.RECOVERY, RuleJobRun.rule_id == rule_id, RuleJobRun.status == "running")
            .count()
            > 0
        )

    def _to_summary(self, rule: RecoveryEventRule) -> RecoveryEventRuleSummary:
        state = self._get_watch_state(rule.id)
        return RecoveryEventRuleSummary(
            id=rule.id,
            name=rule.name,
            namespace=rule.namespace,
            enabled=rule.enabled,
            dbConfig=RecoveryEventRuleComponentDetail(name=rule.db_config.name if rule.db_config else ""),
            s3Config=RecoveryEventRuleComponentDetail(name=rule.s3_config.name if rule.s3_config else ""),
            watcher=RecoveryEventRuleWatcher(
                status=self._resolve_status(rule, state),
                lastPolledAt=state.last_polled_at if state else None,
                lastDbEmptyAt=state.last_db_empty_at if state else None,
                lastS3EmptyAt=state.last_s3_empty_at if state else None,
                lastDbTriggeredAt=state.last_db_triggered_at if state else None,
                lastS3TriggeredAt=state.last_s3_triggered_at if state else None,
                lastErrorAt=state.last_error_at if state else None,
                lastErrorMessage=state.last_error_message if state else None,
            ),
            updatedAt=rule.updated_at,
        )

    def _to_detail(self, rule: RecoveryEventRule) -> RecoveryEventRuleDetail:
        summary = self._to_summary(rule)
        if rule.db_config is None or rule.s3_config is None:
            raise HTTPException(status_code=409, detail="Recovery event rule is not fully configured")
        return RecoveryEventRuleDetail(
            **summary.model_dump(),
            dbConfig=RecoveryEventRuleDbConfigDetail(
                name=rule.db_config.name,
                dbBackupsFilenamePrefix=rule.db_config.db_backups_filename_prefix,
                sourceAwsEndpoint=rule.db_config.source_aws_endpoint,
                sourceAwsBucketName=rule.db_config.source_aws_bucket_name,
                sourceAwsAccessKeyId=rule.db_config.source_aws_access_key_id,
                targetDatabaseHost=rule.db_config.target_database_host,
                targetDatabaseName=rule.db_config.target_database_name,
                targetDatabaseUsername=rule.db_config.target_database_username,
                hasSourceAwsSecretAccessKey=bool(rule.db_config.source_aws_secret_access_key_encrypted),
                hasTargetDatabasePassword=bool(rule.db_config.target_database_password_encrypted),
            ),
            s3Config=RecoveryEventRuleS3ConfigDetail(
                name=rule.s3_config.name,
                s3BackupsFilenamePrefix=rule.s3_config.s3_backups_filename_prefix,
                sourceS3AwsEndpoint=rule.s3_config.source_s3_aws_endpoint,
                sourceS3AwsBucketName=rule.s3_config.source_s3_aws_bucket_name,
                sourceS3AwsAccessKeyId=rule.s3_config.source_s3_aws_access_key_id,
                targetS3AwsEndpoint=rule.s3_config.target_s3_aws_endpoint,
                targetS3AwsBucketName=rule.s3_config.target_s3_aws_bucket_name,
                targetS3AwsBucketSubfolderName=rule.s3_config.target_s3_aws_bucket_subfolder_name or "",
                targetS3AwsAccessKeyId=rule.s3_config.target_s3_aws_access_key_id,
                hasSourceS3AwsSecretAccessKey=bool(rule.s3_config.source_s3_aws_secret_access_key_encrypted),
                hasTargetS3AwsSecretAccessKey=bool(rule.s3_config.target_s3_aws_secret_access_key_encrypted),
            ),
        )

    @staticmethod
    def _db_release_name(rule_id: int) -> str:
        return f"recovery-rule-db-{rule_id}"[:53]

    @staticmethod
    def _s3_release_name(rule_id: int) -> str:
        return f"recovery-rule-s3-{rule_id}"[:53]

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)
