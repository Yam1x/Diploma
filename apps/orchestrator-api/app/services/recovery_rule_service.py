from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.recovery_rule import RecoveryEventRule, RecoveryEventRuleState
from app.models.task import ServiceType, Task, TaskJobRun, TaskSecret, TriggerMode
from app.schemas.recovery_rule import (
    RecoveryEventRuleCreate,
    RecoveryEventRuleDbConfig,
    RecoveryEventRuleDbDetail,
    RecoveryEventRuleDbUpdate,
    RecoveryEventRuleDetail,
    RecoveryEventRuleS3Config,
    RecoveryEventRuleS3Detail,
    RecoveryEventRuleS3Update,
    RecoveryEventRuleSummary,
    RecoveryEventRuleUpdate,
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
        rule = RecoveryEventRule(
            name=payload.name,
            namespace=payload.namespace,
            db_display_name=payload.db.name,
            s3_display_name=payload.s3.name,
            enabled=False,
        )
        self.db.add(rule)
        self.db.flush()

        db_task = self._create_managed_task(rule, ServiceType.DB_RESTORER, payload.db)
        s3_task = self._create_managed_task(rule, ServiceType.S3_RESTORER, payload.s3)
        rule.db_task = db_task
        rule.s3_task = s3_task
        self.db.commit()
        self.db.refresh(rule)

        if payload.enabled:
            return self.enable_rule(rule.id)
        return self._to_detail(self._get_rule_model(rule.id))

    def update_rule(self, rule_id: int, payload: RecoveryEventRuleUpdate) -> RecoveryEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        changes = payload.model_dump(exclude_unset=True)
        desired_enabled = changes.pop("enabled", None)
        reset_state = False
        redeploy = False

        if "name" in changes:
            rule.name = changes["name"]

        if "namespace" in changes:
            namespace = changes["namespace"]
            rule.namespace = namespace
            rule.db_task.namespace = namespace
            rule.s3_task.namespace = namespace
            reset_state = True
            redeploy = True

        if "db" in changes:
            self._apply_db_update(rule, RecoveryEventRuleDbUpdate(**changes["db"]))
            reset_state = True
            redeploy = True

        if "s3" in changes:
            self._apply_s3_update(rule, RecoveryEventRuleS3Update(**changes["s3"]))
            reset_state = True
            redeploy = True

        self._validate_linked_tasks(rule, require_deployed=False)
        if reset_state:
            self._reset_state(rule)

        self.db.commit()

        if desired_enabled is True and not rule.enabled:
            return self.enable_rule(rule.id)
        if desired_enabled is False and rule.enabled:
            return self.disable_rule(rule.id)
        if redeploy and rule.enabled:
            self._deploy_rule(rule)
            return self._to_detail(self._get_rule_model(rule.id))
        return self._to_detail(self._get_rule_model(rule.id))

    def enable_rule(self, rule_id: int) -> RecoveryEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        self._validate_linked_tasks(rule, require_deployed=False)
        rule.enabled = True
        self.db.commit()
        self._deploy_rule(rule)
        return self._to_detail(self._get_rule_model(rule.id))

    def disable_rule(self, rule_id: int) -> RecoveryEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        rule.enabled = False
        self.db.commit()
        self._disable_managed_task(rule.db_task)
        self._disable_managed_task(rule.s3_task)
        return self._to_detail(self._get_rule_model(rule.id))

    def run_rule(self, rule_id: int) -> RecoveryEventRuleDetail:
        return self._run_rule(rule_id, run_db=True, run_s3=True)

    def run_rule_db(self, rule_id: int) -> RecoveryEventRuleDetail:
        return self._run_rule(rule_id, run_db=True, run_s3=False)

    def run_rule_s3(self, rule_id: int) -> RecoveryEventRuleDetail:
        return self._run_rule(rule_id, run_db=False, run_s3=True)

    def delete_rule(self, rule_id: int) -> None:
        rule = self._get_rule_model(rule_id)
        managed_tasks = [rule.db_task, rule.s3_task]

        rule.db_task = None
        rule.s3_task = None
        rule.db_task_id = None
        rule.s3_task_id = None
        for task in managed_tasks:
            if task is not None:
                task.managed_by_recovery_rule_id = None
        self.db.flush()

        for task in managed_tasks:
            if task is None:
                continue
            self.task_service._cleanup_release(task)
            self.task_service._delete_task_model(task)
        self.db.delete(rule)
        self.db.commit()

    def record_rule_error(self, rule: RecoveryEventRule, message: str) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_state(rule)
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
        state = self._ensure_state(rule)
        state.last_polled_at = state.last_polled_at or now
        state.last_error_at = None
        state.last_error_message = None
        if db_job_name:
            state.last_db_triggered_at = now
        if s3_job_name:
            state.last_s3_triggered_at = now
        self.db.flush()
        self.notifications.notify_recovery_event_rule_run_started(
            rule,
            trigger_type=trigger_type,
            db_job_name=db_job_name,
            s3_job_name=s3_job_name,
        )

    def _deploy_rule(self, rule: RecoveryEventRule) -> None:
        try:
            for task in (rule.db_task, rule.s3_task):
                if task is None:
                    continue
                if task.enabled:
                    self.task_service._apply_release(task)
                else:
                    self.task_service.enable_task_model(task)
        except HTTPException as exc:
            self.record_rule_error(rule, str(exc.detail))
            self.db.commit()
            raise

    def _disable_managed_task(self, task: Task | None) -> None:
        if task is None:
            return
        self.task_service._cleanup_release(task)
        task.enabled = False
        task.last_apply_status = "disabled"
        task.last_apply_message = "Release removed"
        task.last_applied_at = datetime.now(timezone.utc)
        self.db.commit()

    def _start_rule_jobs(
        self,
        rule: RecoveryEventRule,
        *,
        trigger_type: str,
        run_db: bool,
        run_s3: bool,
    ) -> None:
        if not run_db and not run_s3:
            return

        db_run = None
        s3_run = None
        operation_name = self._describe_run_operation(run_db=run_db, run_s3=run_s3)
        try:
            if run_db:
                db_run = self.task_service.create_triggered_job_run(rule.db_task, trigger_type=trigger_type)
            if run_s3:
                s3_run = self.task_service.create_triggered_job_run(rule.s3_task, trigger_type=trigger_type)
        except Exception as exc:
            parts: list[str] = []
            if db_run is not None:
                parts.append(f"DB job {db_run.job_name} created")
            if s3_run is not None:
                parts.append(f"S3 job {s3_run.job_name} created")
            prefix = ", ".join(parts)
            if prefix:
                message = f"{operation_name} partially started: {prefix}, but another launch failed: {exc}"
            else:
                message = f"Failed to start {operation_name}: {exc}"
            self.record_rule_error(rule, message)
            self.db.commit()
            raise HTTPException(status_code=502, detail=message) from exc

        self.record_successful_trigger(
            rule,
            trigger_type=trigger_type,
            db_job_name=db_run.job_name if db_run else None,
            s3_job_name=s3_run.job_name if s3_run else None,
        )

    def _run_rule(self, rule_id: int, *, run_db: bool, run_s3: bool) -> RecoveryEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        self._validate_linked_tasks(rule)
        self._start_rule_jobs(rule, trigger_type="manual", run_db=run_db, run_s3=run_s3)
        self.db.commit()
        return self._to_detail(self._get_rule_model(rule.id))

    def _create_managed_task(
        self,
        rule: RecoveryEventRule,
        service_type: ServiceType,
        payload: RecoveryEventRuleDbConfig | RecoveryEventRuleS3Config,
    ) -> Task:
        task = Task(
            name=self._build_managed_task_name(rule.id, service_type),
            namespace=rule.namespace,
            enabled=False,
            service_type=service_type,
            schedule=None,
            trigger_mode=TriggerMode.EVENT_BASED.value,
            release_name="pending",
            managed_by_recovery_rule_id=rule.id,
        )
        task.secret = TaskSecret()
        self.db.add(task)
        self.db.flush()
        task.release_name = self.task_service._build_release_name(task.id, service_type)

        if service_type == ServiceType.DB_RESTORER:
            self._apply_db_config_to_task(task, payload)
        else:
            self._apply_s3_config_to_task(task, payload)

        return task

    def _apply_db_update(self, rule: RecoveryEventRule, payload: RecoveryEventRuleDbUpdate) -> None:
        changes = payload.model_dump(exclude_unset=True)
        if "name" in changes:
            rule.db_display_name = changes["name"]
        self._apply_db_config_to_task(rule.db_task, payload)

    def _apply_s3_update(self, rule: RecoveryEventRule, payload: RecoveryEventRuleS3Update) -> None:
        changes = payload.model_dump(exclude_unset=True)
        if "name" in changes:
            rule.s3_display_name = changes["name"]
        self._apply_s3_config_to_task(rule.s3_task, payload)

    @staticmethod
    def _apply_db_config_to_task(task: Task, payload: RecoveryEventRuleDbConfig | RecoveryEventRuleDbUpdate) -> None:
        changes = payload.model_dump(exclude_unset=True)
        field_map = {
            "dbBackupsFilenamePrefix": "db_backups_filename_prefix",
            "sourceAwsEndpoint": "destination_aws_endpoint",
            "sourceAwsBucketName": "destination_aws_bucket_name",
            "sourceAwsAccessKeyId": "destination_aws_access_key_id",
            "targetDatabaseHost": "database_host",
            "targetDatabaseName": "database_name",
            "targetDatabaseUsername": "database_username",
        }
        for source, target in field_map.items():
            if source in changes:
                setattr(task, target, changes[source])
        if "sourceAwsSecretAccessKey" in changes:
            task.secret.destination_aws_secret_access_key_encrypted = changes["sourceAwsSecretAccessKey"]
        if "targetDatabasePassword" in changes:
            task.secret.database_password_encrypted = changes["targetDatabasePassword"]

    @staticmethod
    def _apply_s3_config_to_task(task: Task, payload: RecoveryEventRuleS3Config | RecoveryEventRuleS3Update) -> None:
        changes = payload.model_dump(exclude_unset=True)
        field_map = {
            "s3BackupsFilenamePrefix": "s3_backups_filename_prefix",
            "sourceS3AwsEndpoint": "source_s3_aws_endpoint",
            "sourceS3AwsBucketName": "source_s3_aws_bucket_name",
            "sourceS3AwsAccessKeyId": "source_s3_aws_access_key_id",
            "targetS3AwsEndpoint": "destination_s3_aws_endpoint",
            "targetS3AwsBucketName": "destination_s3_aws_bucket_name",
            "targetS3AwsBucketSubfolderName": "target_s3_aws_bucket_subfolder_name",
            "targetS3AwsAccessKeyId": "destination_s3_aws_access_key_id",
        }
        for source, target in field_map.items():
            if source in changes:
                setattr(task, target, changes[source] or None)
        if "sourceS3AwsSecretAccessKey" in changes:
            task.secret.source_s3_aws_secret_access_key_encrypted = changes["sourceS3AwsSecretAccessKey"]
        if "targetS3AwsSecretAccessKey" in changes:
            task.secret.destination_s3_aws_secret_access_key_encrypted = changes["targetS3AwsSecretAccessKey"]

    def _get_rule_model(self, rule_id: int) -> RecoveryEventRule:
        rule = self.db.query(RecoveryEventRule).options(*self._rule_load_options()).filter(RecoveryEventRule.id == rule_id).one_or_none()
        if rule is None:
            raise HTTPException(status_code=404, detail="Recovery event rule not found")
        if rule.db_task is None or rule.s3_task is None:
            raise HTTPException(status_code=409, detail="Recovery event rule is not fully configured")
        return rule

    @staticmethod
    def _rule_load_options():
        return (
            joinedload(RecoveryEventRule.db_task).joinedload(Task.secret),
            joinedload(RecoveryEventRule.s3_task).joinedload(Task.secret),
            joinedload(RecoveryEventRule.state),
        )

    def _validate_linked_tasks(self, rule: RecoveryEventRule, require_deployed: bool = True) -> None:
        db_task = rule.db_task
        s3_task = rule.s3_task
        if db_task is None or s3_task is None:
            raise HTTPException(status_code=409, detail="Recovery event rule is not fully configured")
        if db_task.id == s3_task.id:
            raise HTTPException(status_code=400, detail="DB and S3 tasks must be different")
        if db_task.service_type != ServiceType.DB_RESTORER:
            raise HTTPException(status_code=400, detail="Rule DB config must map to a db_restorer task")
        if s3_task.service_type != ServiceType.S3_RESTORER:
            raise HTTPException(status_code=400, detail="Rule S3 config must map to a s3_restorer task")
        for task in (db_task, s3_task):
            if task.managed_by_recovery_rule_id != rule.id:
                raise HTTPException(status_code=400, detail="Linked tasks must be managed by the recovery rule")
            if task.trigger_mode != TriggerMode.EVENT_BASED.value:
                raise HTTPException(status_code=400, detail="Linked tasks must use event_based trigger mode")
            if task.namespace != rule.namespace:
                raise HTTPException(status_code=400, detail="Linked tasks must use the recovery rule namespace")
            if require_deployed:
                if not task.enabled:
                    raise HTTPException(status_code=400, detail="Linked tasks must be enabled")
                if task.last_apply_status != "deployed" or not task.release_name:
                    raise HTTPException(status_code=400, detail="Linked tasks must be deployed")

    def _ensure_state(self, rule: RecoveryEventRule) -> RecoveryEventRuleState:
        if rule.state is not None:
            return rule.state

        state = RecoveryEventRuleState(rule=rule)
        self.db.add(state)
        self.db.flush()
        return state

    def _reset_state(self, rule: RecoveryEventRule) -> None:
        if rule.state is None:
            return
        self.db.delete(rule.state)
        self.db.flush()

    def _resolve_status(self, rule: RecoveryEventRule) -> str:
        if not rule.enabled:
            return "disabled"
        if (
            rule.db_task is None
            or rule.s3_task is None
            or not rule.db_task.enabled
            or not rule.s3_task.enabled
            or rule.db_task.last_apply_status != "deployed"
            or rule.s3_task.last_apply_status != "deployed"
        ):
            return "error"

        if self._has_running_runs(rule):
            return "restoring"

        state = rule.state
        if state is None or state.last_polled_at is None:
            return "waiting_for_baseline"
        if state.last_error_at and state.last_error_at >= state.last_polled_at:
            return "error"

        cooldown_cutoff = datetime.now(timezone.utc).timestamp() - self.task_service.settings.event_watcher_cooldown_seconds
        last_db_triggered_at = self._normalize_datetime(state.last_db_triggered_at)
        last_s3_triggered_at = self._normalize_datetime(state.last_s3_triggered_at)
        if (
            last_db_triggered_at and last_db_triggered_at.timestamp() >= cooldown_cutoff
        ) or (
            last_s3_triggered_at and last_s3_triggered_at.timestamp() >= cooldown_cutoff
        ):
            return "cooldown"
        return "watching"

    def _has_running_runs(self, rule: RecoveryEventRule) -> bool:
        task_ids = [task.id for task in (rule.db_task, rule.s3_task) if task is not None]
        if not task_ids:
            return False
        running = (
            self.db.query(TaskJobRun)
            .filter(TaskJobRun.task_id.in_(task_ids), TaskJobRun.status == "running")
            .count()
        )
        return running > 0

    def _to_summary(self, rule: RecoveryEventRule) -> RecoveryEventRuleSummary:
        state = rule.state
        return RecoveryEventRuleSummary(
            id=rule.id,
            name=rule.name,
            namespace=rule.namespace,
            enabled=rule.enabled,
            dbName=rule.db_display_name,
            s3Name=rule.s3_display_name,
            eventWatcherStatus=self._resolve_status(rule),
            lastPolledAt=state.last_polled_at if state else None,
            lastDbEmptyAt=state.last_db_empty_at if state else None,
            lastS3EmptyAt=state.last_s3_empty_at if state else None,
            lastDbTriggeredAt=state.last_db_triggered_at if state else None,
            lastS3TriggeredAt=state.last_s3_triggered_at if state else None,
            lastErrorAt=state.last_error_at if state else None,
            lastErrorMessage=state.last_error_message if state else None,
            updatedAt=rule.updated_at,
        )

    def _to_detail(self, rule: RecoveryEventRule) -> RecoveryEventRuleDetail:
        state = rule.state
        db_task = rule.db_task
        s3_task = rule.s3_task
        if db_task is None or s3_task is None:
            raise HTTPException(status_code=409, detail="Recovery event rule is not fully configured")

        return RecoveryEventRuleDetail(
            **self._to_summary(rule).model_dump(),
            db=RecoveryEventRuleDbDetail(
                name=rule.db_display_name,
                dbBackupsFilenamePrefix=db_task.db_backups_filename_prefix or "",
                sourceAwsEndpoint=db_task.destination_aws_endpoint or "",
                sourceAwsBucketName=db_task.destination_aws_bucket_name or "",
                sourceAwsAccessKeyId=db_task.destination_aws_access_key_id or "",
                targetDatabaseHost=db_task.database_host or "",
                targetDatabaseName=db_task.database_name or "",
                targetDatabaseUsername=db_task.database_username or "",
                hasSourceAwsSecretAccessKey=bool(db_task.secret.destination_aws_secret_access_key_encrypted),
                hasTargetDatabasePassword=bool(db_task.secret.database_password_encrypted),
            ),
            s3=RecoveryEventRuleS3Detail(
                name=rule.s3_display_name,
                s3BackupsFilenamePrefix=s3_task.s3_backups_filename_prefix or "",
                sourceS3AwsEndpoint=s3_task.source_s3_aws_endpoint or "",
                sourceS3AwsBucketName=s3_task.source_s3_aws_bucket_name or "",
                sourceS3AwsAccessKeyId=s3_task.source_s3_aws_access_key_id or "",
                targetS3AwsEndpoint=s3_task.destination_s3_aws_endpoint or "",
                targetS3AwsBucketName=s3_task.destination_s3_aws_bucket_name or "",
                targetS3AwsBucketSubfolderName=s3_task.target_s3_aws_bucket_subfolder_name or "",
                targetS3AwsAccessKeyId=s3_task.destination_s3_aws_access_key_id or "",
                hasSourceS3AwsSecretAccessKey=bool(s3_task.secret.source_s3_aws_secret_access_key_encrypted),
                hasTargetS3AwsSecretAccessKey=bool(s3_task.secret.destination_s3_aws_secret_access_key_encrypted),
            ),
        )

    @staticmethod
    def _build_managed_task_name(rule_id: int, service_type: ServiceType) -> str:
        suffix = "db" if service_type == ServiceType.DB_RESTORER else "s3"
        return f"recovery-rule-{rule_id}-{suffix}"

    @staticmethod
    def _describe_run_operation(*, run_db: bool, run_s3: bool) -> str:
        if run_db and run_s3:
            return "Combined recovery"
        if run_db:
            return "DB recovery"
        return "S3 recovery"

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)
