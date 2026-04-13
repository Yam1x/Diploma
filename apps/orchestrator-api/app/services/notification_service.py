from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.task import Task, TaskJobRun
from app.schemas.notification import NotificationItem, NotificationsResponse


class NotificationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_notifications(self, limit: int = 20, unread_only: bool = False) -> NotificationsResponse:
        query = self.db.query(Notification)
        if unread_only:
            query = query.filter(Notification.is_read.is_(False))

        items = (
            query.order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
            .all()
        )
        unread_count = self.db.query(Notification).filter(Notification.is_read.is_(False)).count()

        return NotificationsResponse(
            unreadCount=unread_count,
            items=[self._to_item(notification) for notification in items],
        )

    def mark_read(self, notification_id: int) -> None:
        notification = self.db.query(Notification).filter(Notification.id == notification_id).one_or_none()
        if notification is None:
            raise HTTPException(status_code=404, detail="Notification not found")

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            self.db.commit()

    def mark_all_read(self) -> None:
        now = datetime.now(timezone.utc)
        notifications = self.db.query(Notification).filter(Notification.is_read.is_(False)).all()

        if not notifications:
            return

        for notification in notifications:
            notification.is_read = True
            notification.read_at = now

        self.db.commit()

    def create_notification(
        self,
        *,
        event_key: str,
        kind: str,
        severity: str,
        title: str,
        message: str,
        task_id: int | None = None,
        job_run_id: int | None = None,
        link_path: str | None = None,
    ) -> Notification:
        existing = self.db.query(Notification).filter(Notification.event_key == event_key).one_or_none()
        if existing is not None:
            return existing

        notification = Notification(
            event_key=event_key,
            kind=kind,
            severity=severity,
            title=title,
            message=message,
            task_id=task_id,
            job_run_id=job_run_id,
            link_path=link_path,
            is_read=False,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def notify_task_deploy_failed(self, task: Task) -> None:
        message = task.last_apply_message or "Не удалось применить release"
        self.create_notification(
            event_key=self._event_key("task", task.id, "deploy-failed", message),
            kind="task_deploy_failed",
            severity="error",
            title=f"Ошибка деплоя: {task.name}",
            message=message,
            task_id=task.id,
            link_path=f"/tasks/{task.id}",
        )

    def notify_task_missing(self, task: Task) -> None:
        message = task.last_apply_message or "Release не найден"
        self.create_notification(
            event_key=self._event_key("task", task.id, "missing", message),
            kind="task_missing",
            severity="warning",
            title=f"Release не найден: {task.name}",
            message=message,
            task_id=task.id,
            link_path=f"/tasks/{task.id}",
        )

    def notify_task_attention_required(self, task: Task, reason: str) -> None:
        self.create_notification(
            event_key=self._event_key("task", task.id, "attention", reason),
            kind="task_attention_required",
            severity="warning",
            title=f"Требуется внимание: {task.name}",
            message=f"Задача включена, но требует проверки. Причина: {reason}.",
            task_id=task.id,
            link_path=f"/tasks/{task.id}",
        )

    def notify_manual_run_started(self, task: Task, run: TaskJobRun) -> None:
        self.create_notification(
            event_key=self._event_key("task", task.id, "manual-run-started", run.job_name),
            kind="task_manual_run_started",
            severity="info",
            title=f"Ручной запуск начат: {task.name}",
            message=f"Создан job {run.job_name}.",
            task_id=task.id,
            job_run_id=run.id,
            link_path=f"/tasks/{task.id}",
        )

    def notify_event_run_started(self, task: Task, run: TaskJobRun) -> None:
        self.create_notification(
            event_key=self._event_key("task", task.id, "event-run-started", run.job_name),
            kind="task_event_run_started",
            severity="info",
            title=f"Событийный запуск начат: {task.name}",
            message=f"Создан job {run.job_name}.",
            task_id=task.id,
            job_run_id=run.id,
            link_path=f"/tasks/{task.id}",
        )

    def notify_event_watcher_issue(self, task: Task, message: str) -> None:
        self.create_notification(
            event_key=self._event_key("task", task.id, "event-watcher-issue", message),
            kind="task_event_watcher_issue",
            severity="warning",
            title=f"Проблема event watcher: {task.name}",
            message=message,
            task_id=task.id,
            link_path=f"/tasks/{task.id}",
        )

    def notify_job_run_status(self, task: Task, run: TaskJobRun) -> None:
        if run.status not in {"failed", "succeeded"}:
            return

        kind = "job_run_failed" if run.status == "failed" else "job_run_succeeded"
        severity = "error" if run.status == "failed" else "success"
        title = f"Запуск завершился с ошибкой: {task.name}" if run.status == "failed" else f"Запуск завершился успешно: {task.name}"
        message = f"Job {run.job_name} завершился со статусом {run.status}."

        self.create_notification(
            event_key=self._event_key("job-run", run.namespace, run.job_name, run.status),
            kind=kind,
            severity=severity,
            title=title,
            message=message,
            task_id=task.id,
            job_run_id=run.id,
            link_path=f"/tasks/{task.id}",
        )

    @staticmethod
    def _to_item(notification: Notification) -> NotificationItem:
        return NotificationItem(
            id=notification.id,
            kind=notification.kind,
            severity=notification.severity,
            title=notification.title,
            message=notification.message,
            taskId=notification.task_id,
            jobRunId=notification.job_run_id,
            linkPath=notification.link_path,
            isRead=notification.is_read,
            readAt=notification.read_at,
            createdAt=notification.created_at,
        )

    @staticmethod
    def _event_key(*parts: object) -> str:
        raw = "::".join("" if part is None else str(part) for part in parts)
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        prefix = str(parts[0]) if parts else "event"
        return f"{prefix}:{digest}"
