from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.recovery_rule import (
    RecoveryEventRule,
    RecoveryEventRuleSecret,
    RecoveryEventRuleS3Secret,
    RecoveryEventRuleState,
)
from app.models.task import ServiceType, Task, TaskJobRun, TaskSecret, TriggerMode
from app.schemas.recovery_rule import (
    RecoveryEventRuleCreate,
    RecoveryEventRuleDbDetail,
    RecoveryRuleDbUpdateConfig,
    RecoveryEventRuleDetail,
    RecoveryEventRuleS3Detail,
    RecoveryRuleS3UpdateConfig,
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
            db_display_name=payload.db.backupsFilenamePrefix,
            s3_display_name=payload.s3.backupsFilenamePrefix,
            enabled=False,
            db_config=self._build_db_config(payload.db),
            s3_config=self._build_s3_config(payload.s3),
        )
        self.db.add(rule)
        self.db.flush()

        db_task = self._create_managed_task(rule, ServiceType.DB_RESTORER, rule.db_config)
        s3_task = self._create_managed_task(rule, ServiceType.S3_RESTORER, rule.s3_config)
        rule.db_task = db_task
        rule.s3_task = s3_task

        db_secret = RecoveryEventRuleSecret(
            rule_id=rule.id,
            source_secret_encrypted=payload.db.sourceSecretAccessKey,
            destination_secret_encrypted=payload.db.destinationPassword,
        )
        s3_secret = RecoveryEventRuleS3Secret(
            rule_id=rule.id,
            source_secret_encrypted=payload.s3.sourceSecretAccessKey,
            destination_secret_encrypted=payload.s3.destinationSecretAccessKey,
        )
        self.db.add(db_secret)
        self.db.add(s3_secret)

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

        if "db" in changes and changes["db"] is not None:
            db_changes = changes["db"]
            new_config = {**(rule.db_config or {}), **db_changes}
            rule.db_config = new_config
            self._apply_db_config_to_task(rule.db_task, new_config)
            self._apply_db_secret_to_task(rule.db_task, db_changes)
            rule.db_display_name = db_changes.get("backupsFilenamePrefix", rule.db_display_name)
            reset_state = True
            redeploy = True

        if "s3" in changes and changes["s3"] is not None:
            s3_changes = changes["s3"]
            new_config = {**(rule.s3_config or {}), **s3_changes}
            rule.s3_config = new_config
            self._apply_s3_config_to_task(rule.s3_task, new_config)
            self._apply_s3_secret_to_task(rule.s3_task, s3_changes)
            rule.s3_display_name = s3_changes.get("backupsFilenamePrefix", rule.s3_display_name)
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

    def _create_managed_task(self, rule: RecoveryEventRule, service_type: ServiceType, config: dict) -> Task:
        task = Task(
            name=self._build_managed_task_name(rule.id, service_type),
            namespace=rule.namespace,
            enabled=False,
            service_type=service_type,
            schedule=None,
            trigger_mode=TriggerMode.EVENT_BASED.value,
            release_name="pending",
            managed_by_recovery_rule_id=rule.id,
            config=config,
        )
        task.secret = TaskSecret()
        self.db.add(task)
        self.db.flush()
        task.release_name = self.task_service._build_release_name(task.id, service_type)
        return task

    def _build_db_config(self, payload: RecoveryEventRuleCreate) -> dict:
        return {
            "filenamePrefix": payload.backupsFilenamePrefix,
            "source": {
                "endpoint": payload.sourceEndpoint,
                "bucketName": payload.sourceBucketName,
                "accessKeyId": payload.sourceAccessKeyId,
            },
            "destination": {
                "host": payload.destinationHost,
                "name": payload.destinationName,
                "username": payload.destinationUsername,
            },
        }

    def _build_s3_config(self, payload: RecoveryEventRuleCreate) -> dict:
        return {
            "filenamePrefix": payload.backupsFilenamePrefix,
            "source": {
                "endpoint": payload.sourceEndpoint,
                "bucketName": payload.sourceBucketName,
                "accessKeyId": payload.sourceAccessKeyId,
            },
            "destination": {
                "endpoint": payload.destinationEndpoint,
                "bucketName": payload.destinationBucketName,
                "accessKeyId": payload.destinationAccessKeyId,
                "subfolderName": payload.destinationSubfolderName,
            },
        }

    @staticmethod
    def _apply_db_config_to_task(task: Task, config: dict) -> None:
        task.config = config

    @staticmethod
    def _apply_s3_config_to_task(task: Task, config: dict) -> None:
        task.config = config

    @staticmethod
    def _apply_db_secret_to_task(task: Task, changes: dict) -> None:
        if "sourceSecretAccessKey" in changes and changes["sourceSecretAccessKey"] is not None:
            task.secret.source_secret_encrypted = changes["sourceSecretAccessKey"]
        if "destinationPassword" in changes and changes["destinationPassword"] is not None:
            task.secret.destination_secret_encrypted = changes["destinationPassword"]

    @staticmethod
    def _apply_s3_secret_to_task(task: Task, changes: dict) -> None:
        if "sourceSecretAccessKey" in changes and changes["sourceSecretAccessKey"] is not None:
            task.secret.source_secret_encrypted = changes["sourceSecretAccessKey"]
        if "destinationSecretAccessKey" in changes and changes["destinationSecretAccessKey"] is not None:
            task.secret.destination_secret_encrypted = changes["destinationSecretAccessKey"]

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

        db_config = db_task.config or {}
        db_source = db_config.get("source", {})
        db_dest = db_config.get("destination", {})

        s3_config = s3_task.config or {}
        s3_source = s3_config.get("source", {})
        s3_dest = s3_config.get("destination", {})

        db_source_secret = db_task.secret.source_secret_encrypted if db_task.secret else None
        db_dest_secret = db_task.secret.destination_secret_encrypted if db_task.secret else None
        s3_source_secret = s3_task.secret.source_secret_encrypted if s3_task.secret else None
        s3_dest_secret = s3_task.secret.destination_secret_encrypted if s3_task.secret else None

        return RecoveryEventRuleDetail(
            **self._to_summary(rule).model_dump(),
            db=RecoveryEventRuleDbDetail(
                name=rule.db_display_name,
                backupsFilenamePrefix=db_config.get("filenamePrefix", ""),
                sourceEndpoint=db_source.get("endpoint", ""),
                sourceBucketName=db_source.get("bucketName", ""),
                sourceAccessKeyId=db_source.get("accessKeyId", ""),
                destinationHost=db_dest.get("host", ""),
                destinationName=db_dest.get("name", ""),
                destinationUsername=db_dest.get("username", ""),
                hasSourceSecret=bool(db_source_secret),
                hasDestinationPassword=bool(db_dest_secret),
            ),
            s3=RecoveryEventRuleS3Detail(
                name=rule.s3_display_name,
                backupsFilenamePrefix=s3_config.get("filenamePrefix", ""),
                sourceEndpoint=s3_source.get("endpoint", ""),
                sourceBucketName=s3_source.get("bucketName", ""),
                sourceAccessKeyId=s3_source.get("accessKeyId", ""),
                destinationEndpoint=s3_dest.get("endpoint", ""),
                destinationBucketName=s3_dest.get("bucketName", ""),
                destinationSubfolderName=s3_dest.get("subfolderName", ""),
                destinationAccessKeyId=s3_dest.get("accessKeyId", ""),
                hasSourceSecret=bool(s3_source_secret),
                hasDestinationSecret=bool(s3_dest_secret),
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