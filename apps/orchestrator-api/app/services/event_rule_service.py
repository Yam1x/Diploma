from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.event_rule import BackupEventRule, BackupEventRuleState
from app.models.task import ServiceType, Task, TriggerMode
from app.schemas.event_rule import BackupEventRuleCreate, BackupEventRuleDetail, BackupEventRuleSummary, BackupEventRuleUpdate
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
        db_task = self._get_task(payload.dbTaskId)
        s3_task = self._get_task(payload.s3TaskId)
        self._validate_linked_tasks(db_task, s3_task)

        rule = BackupEventRule(
            name=payload.name,
            enabled=False,
            db_task_id=db_task.id,
            s3_task_id=s3_task.id,
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
        reset_state = False

        if "name" in changes:
            rule.name = changes["name"]

        if "dbTaskId" in changes:
            rule.db_task = self._get_task(changes["dbTaskId"])
            rule.db_task_id = rule.db_task.id
            reset_state = True

        if "s3TaskId" in changes:
            rule.s3_task = self._get_task(changes["s3TaskId"])
            rule.s3_task_id = rule.s3_task.id
            reset_state = True

        self._validate_linked_tasks(rule.db_task, rule.s3_task)
        if reset_state:
            self._reset_state(rule)

        self.db.commit()

        if desired_enabled is True and not rule.enabled:
            return self.enable_rule(rule.id)
        if desired_enabled is False and rule.enabled:
            return self.disable_rule(rule.id)
        return self._to_detail(self._get_rule_model(rule.id))

    def enable_rule(self, rule_id: int) -> BackupEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        self._validate_linked_tasks(rule.db_task, rule.s3_task)
        rule.enabled = True
        self.db.commit()
        return self._to_detail(self._get_rule_model(rule.id))

    def disable_rule(self, rule_id: int) -> BackupEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        rule.enabled = False
        self.db.commit()
        return self._to_detail(self._get_rule_model(rule.id))

    def run_rule(self, rule_id: int) -> BackupEventRuleDetail:
        rule = self._get_rule_model(rule_id)
        self._validate_linked_tasks(rule.db_task, rule.s3_task)
        self._start_rule_jobs(rule, trigger_type="manual")
        self.db.commit()
        return self._to_detail(self._get_rule_model(rule.id))

    def delete_rule(self, rule_id: int) -> None:
        rule = self._get_rule_model(rule_id)
        self.db.delete(rule)
        self.db.commit()

    def record_rule_error(self, rule: BackupEventRule, message: str) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_state(rule)
        state.last_polled_at = now
        state.last_error_at = now
        state.last_error_message = message
        self.db.flush()
        self.notifications.notify_backup_event_rule_issue(rule, message)

    def record_successful_trigger(self, rule: BackupEventRule, *, trigger_type: str, db_job_name: str, s3_job_name: str) -> None:
        now = datetime.now(timezone.utc)
        state = self._ensure_state(rule)
        state.last_polled_at = state.last_polled_at or now
        state.last_error_at = None
        state.last_error_message = None
        state.last_triggered_at = now
        self.db.flush()
        self.notifications.notify_backup_event_rule_run_started(
            rule,
            trigger_type=trigger_type,
            db_job_name=db_job_name,
            s3_job_name=s3_job_name,
        )

    def _start_rule_jobs(self, rule: BackupEventRule, *, trigger_type: str) -> None:
        db_run = None
        try:
            db_run = self.task_service.create_triggered_job_run(rule.db_task, trigger_type=trigger_type)
            s3_run = self.task_service.create_triggered_job_run(rule.s3_task, trigger_type=trigger_type)
        except Exception as exc:
            if db_run is not None:
                message = f"Combined backup partially started: DB job {db_run.job_name} created, but S3 launch failed: {exc}"
            else:
                message = f"Failed to start combined backup: {exc}"
            self.record_rule_error(rule, message)
            self.db.commit()
            raise HTTPException(status_code=502, detail=message) from exc

        self.record_successful_trigger(
            rule,
            trigger_type=trigger_type,
            db_job_name=db_run.job_name,
            s3_job_name=s3_run.job_name,
        )

    def _get_rule_model(self, rule_id: int) -> BackupEventRule:
        rule = self.db.query(BackupEventRule).options(*self._rule_load_options()).filter(BackupEventRule.id == rule_id).one_or_none()
        if rule is None:
            raise HTTPException(status_code=404, detail="Backup event rule not found")
        return rule

    def _get_task(self, task_id: int) -> Task:
        task = self.db.query(Task).options(joinedload(Task.secret), joinedload(Task.event_watch_state)).filter(Task.id == task_id).one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return task

    @staticmethod
    def _rule_load_options():
        return (
            joinedload(BackupEventRule.db_task).joinedload(Task.secret),
            joinedload(BackupEventRule.db_task).joinedload(Task.event_watch_state),
            joinedload(BackupEventRule.s3_task).joinedload(Task.secret),
            joinedload(BackupEventRule.s3_task).joinedload(Task.event_watch_state),
            joinedload(BackupEventRule.state),
        )

    def _validate_linked_tasks(self, db_task: Task, s3_task: Task) -> None:
        if db_task.id == s3_task.id:
            raise HTTPException(status_code=400, detail="DB and S3 tasks must be different")
        if db_task.service_type != ServiceType.DB_BACKUPPER:
            raise HTTPException(status_code=400, detail="dbTaskId must reference a db_backupper task")
        if s3_task.service_type != ServiceType.S3_BACKUPPER:
            raise HTTPException(status_code=400, detail="s3TaskId must reference a s3_backupper task")
        for task in (db_task, s3_task):
            if task.trigger_mode != TriggerMode.EVENT_BASED.value:
                raise HTTPException(status_code=400, detail="Linked tasks must use event_based trigger mode")
            if not task.enabled:
                raise HTTPException(status_code=400, detail="Linked tasks must be enabled")
            if task.last_apply_status != "deployed" or not task.release_name:
                raise HTTPException(status_code=400, detail="Linked tasks must be deployed")

    def _ensure_state(self, rule: BackupEventRule) -> BackupEventRuleState:
        if rule.state is not None:
            return rule.state

        state = BackupEventRuleState(rule=rule)
        self.db.add(state)
        self.db.flush()
        return state

    def _reset_state(self, rule: BackupEventRule) -> None:
        if rule.state is None:
            return
        self.db.delete(rule.state)
        self.db.flush()

    def _resolve_status(self, rule: BackupEventRule) -> str:
        if not rule.enabled:
            return "disabled"

        state = rule.state
        if state is None or state.last_polled_at is None:
            return "waiting_for_baseline"
        if state.last_error_at and state.last_error_at >= state.last_polled_at:
            return "error"

        cooldown_cutoff = datetime.now(timezone.utc).timestamp() - self.task_service.settings.event_watcher_cooldown_seconds
        if state.last_triggered_at and self._normalize_datetime(state.last_triggered_at).timestamp() >= cooldown_cutoff:
            return "cooldown"
        return "watching"

    def _to_summary(self, rule: BackupEventRule) -> BackupEventRuleSummary:
        state = rule.state
        return BackupEventRuleSummary(
            id=rule.id,
            name=rule.name,
            enabled=rule.enabled,
            dbTaskId=rule.db_task_id,
            dbTaskName=rule.db_task.name,
            s3TaskId=rule.s3_task_id,
            s3TaskName=rule.s3_task.name,
            eventWatcherStatus=self._resolve_status(rule),
            lastTriggeredAt=state.last_triggered_at if state else None,
            updatedAt=rule.updated_at,
        )

    def _to_detail(self, rule: BackupEventRule) -> BackupEventRuleDetail:
        state = rule.state
        return BackupEventRuleDetail(
            **self._to_summary(rule).model_dump(),
            lastPolledAt=state.last_polled_at if state else None,
            lastDbChangeAt=state.last_db_change_at if state else None,
            lastS3ChangeAt=state.last_s3_change_at if state else None,
            lastErrorAt=state.last_error_at if state else None,
            lastErrorMessage=state.last_error_message if state else None,
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)
