from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.kube import KubeClient, KubernetesError
from app.models.task import Task, TaskJobRun
from app.schemas.stats import DashboardStatsResponse, JobRunLogsResponse, JobRunSummary, JobsStats, StorageStats, TaskJobRunsResponse, TaskJobStats
from app.services.minio_browser_service import MinioBrowserService
from app.services.notification_service import NotificationService


class StatsService:
    def __init__(
        self,
        db: Session,
        kube: KubeClient | None = None,
        minio: MinioBrowserService | None = None,
        notifications: NotificationService | None = None,
    ) -> None:
        self.db = db
        self.kube = kube or KubeClient()
        self.minio = minio or MinioBrowserService()
        self.notifications = notifications or NotificationService(db)
        self.settings = get_settings()

    def get_dashboard_stats(self) -> DashboardStatsResponse:
        tasks = self.db.query(Task).filter(Task.managed_by_rule_id.is_(None)).order_by(Task.name.asc()).all()
        self._sync_job_history(tasks)

        task_ids = [task.id for task in tasks]
        runs = self._load_runs(task_ids)

        storage_summary = self.minio.get_usage_summary()
        storage = StorageStats(
            bucketName=self.settings.minio_bucket_name,
            objectCount=storage_summary["objectCount"],
            totalSize=storage_summary["totalSize"],
        )

        runs_by_task_id: dict[int, list[TaskJobRun]] = {task.id: [] for task in tasks}
        for run in runs:
            runs_by_task_id.setdefault(run.task_id, []).append(run)

        task_stats = [self._build_task_stats(task, runs_by_task_id.get(task.id, [])) for task in tasks]
        recent_runs = [self._to_run_summary(run) for run in runs[:10]]

        jobs = JobsStats(
            totalRuns=len(runs),
            manualRuns=sum(1 for run in runs if run.trigger_type == "manual"),
            scheduledRuns=sum(1 for run in runs if run.trigger_type == "scheduled"),
            eventRuns=sum(1 for run in runs if run.trigger_type == "event"),
            succeededRuns=sum(1 for run in runs if run.status == "succeeded"),
            failedRuns=sum(1 for run in runs if run.status == "failed"),
            activeRuns=sum(1 for run in runs if run.status == "running"),
            unknownRuns=sum(1 for run in runs if run.status == "unknown"),
            recentRuns=recent_runs,
            tasks=task_stats,
        )

        return DashboardStatsResponse(storage=storage, jobs=jobs)

    def list_task_job_runs(self, task_id: int, limit: int = 10) -> TaskJobRunsResponse:
        task = self._get_task(task_id)
        self._sync_job_history([task])
        runs = self._load_runs([task.id], limit=limit)
        return TaskJobRunsResponse(runs=[self._to_run_summary(run) for run in runs])

    def get_task_job_run_logs(self, task_id: int, run_id: int) -> JobRunLogsResponse:
        task = self._get_task(task_id)
        run = self._get_run(task.id, run_id)
        logs = self._resolve_run_logs(run, task)
        return JobRunLogsResponse(run=self._to_run_summary(run), logs=logs)

    def _sync_job_history(self, tasks: list[Task]) -> None:
        if not tasks:
            return

        now = datetime.now(timezone.utc)
        jobs_by_namespace = self._load_jobs_by_namespace(tasks)
        existing_runs = self._load_existing_run_map(tasks)
        changed = False

        for task in tasks:
            release_name = task.release_name
            if not release_name:
                continue

            manual_prefix = f"{release_name}-manual-"
            event_prefix = f"{release_name}-event-"
            scheduled_prefix = f"{release_name}-"

            for job in jobs_by_namespace.get(task.namespace, []):
                job_name = str(job.get("name", ""))
                if not job_name.startswith(scheduled_prefix):
                    continue

                run = existing_runs.get((task.namespace, job_name))
                status = self._resolve_job_status(job)
                if job_name.startswith(manual_prefix):
                    trigger_type = "manual"
                elif job_name.startswith(event_prefix):
                    trigger_type = "event"
                else:
                    trigger_type = "scheduled"
                started_at = job.get("startTime")
                completed_at = job.get("completionTime")

                if run is None:
                    run = TaskJobRun(
                        task_id=task.id,
                        namespace=task.namespace,
                        release_name=release_name,
                        job_name=job_name,
                        trigger_type=trigger_type,
                        status=status,
                        started_at=started_at,
                        completed_at=completed_at,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                    self.db.add(run)
                    self.db.flush()
                    existing_runs[(task.namespace, job_name)] = run
                    changed = self._capture_logs_if_available(run, task) or changed
                    self.notifications.notify_job_run_status(task, run)
                    changed = True
                    continue

                previous_status = run.status
                changed = self._update_run(run, task, trigger_type, status, started_at, completed_at, now) or changed
                changed = self._capture_logs_if_available(run, task) or changed
                if previous_status != run.status:
                    self.notifications.notify_job_run_status(task, run)

        if changed:
            self.db.commit()

    def _load_jobs_by_namespace(self, tasks: list[Task]) -> dict[str, list[dict]]:
        namespaces = sorted({task.namespace for task in tasks if task.release_name})
        jobs_by_namespace: dict[str, list[dict]] = {}

        for namespace in namespaces:
            try:
                jobs_by_namespace[namespace] = self.kube.list_jobs(namespace)
            except KubernetesError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        return jobs_by_namespace

    def _load_existing_run_map(self, tasks: list[Task]) -> dict[tuple[str, str], TaskJobRun]:
        task_ids = [task.id for task in tasks]
        if not task_ids:
            return {}

        runs = (
            self.db.query(TaskJobRun)
            .filter(TaskJobRun.task_id.in_(task_ids))
            .all()
        )
        return {(run.namespace, run.job_name): run for run in runs}

    def _load_runs(self, task_ids: list[int], limit: int | None = None) -> list[TaskJobRun]:
        if not task_ids:
            return []

        query = (
            self.db.query(TaskJobRun)
            .options(joinedload(TaskJobRun.task))
            .filter(TaskJobRun.task_id.in_(task_ids))
            .order_by(
                TaskJobRun.started_at.desc().nullslast(),
                TaskJobRun.completed_at.desc().nullslast(),
                TaskJobRun.created_at.desc(),
                TaskJobRun.job_name.desc(),
            )
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def _resolve_job_status(job: dict) -> str:
        if int(job.get("active", 0) or 0) > 0:
            return "running"
        if int(job.get("succeeded", 0) or 0) > 0:
            return "succeeded"
        if int(job.get("failed", 0) or 0) > 0:
            return "failed"
        return "unknown"

    @staticmethod
    def _update_run(
        run: TaskJobRun,
        task: Task,
        trigger_type: str,
        status: str,
        started_at: datetime | None,
        completed_at: datetime | None,
        seen_at: datetime,
    ) -> bool:
        changed = False

        if run.task_id != task.id:
            run.task_id = task.id
            changed = True
        if run.release_name != task.release_name:
            run.release_name = task.release_name
            changed = True
        if run.trigger_type != trigger_type:
            run.trigger_type = trigger_type
            changed = True
        if run.status != status:
            run.status = status
            changed = True
        if started_at is not None and run.started_at != started_at:
            run.started_at = started_at
            changed = True
        if completed_at is not None and run.completed_at != completed_at:
            run.completed_at = completed_at
            changed = True
        if run.last_seen_at != seen_at:
            run.last_seen_at = seen_at
            changed = True

        return changed

    def _resolve_run_logs(self, run: TaskJobRun, task: Task) -> str:
        if run.status == "running" or not run.logs_text:
            try:
                live_logs = self.kube.get_job_logs(task.namespace, run.job_name)
            except KubernetesError as exc:
                if run.logs_text:
                    return run.logs_text
                raise HTTPException(status_code=502, detail=str(exc)) from exc

            self._store_run_logs(run, live_logs)
            self.db.commit()
            return live_logs

        return run.logs_text

    def _capture_logs_if_available(self, run: TaskJobRun, task: Task) -> bool:
        if run.status == "running":
            return False

        try:
            logs = self.kube.get_job_logs(task.namespace, run.job_name)
        except KubernetesError:
            return False

        return self._store_run_logs(run, logs)

    @staticmethod
    def _store_run_logs(run: TaskJobRun, logs: str) -> bool:
        normalized_logs = logs.strip()
        changed = False

        if run.logs_text != normalized_logs:
            run.logs_text = normalized_logs
            changed = True
        if run.logs_collected_at is None or changed:
            run.logs_collected_at = datetime.now(timezone.utc)
            changed = True

        return changed

    def _get_task(self, task_id: int) -> Task:
        task = self.db.query(Task).filter(Task.id == task_id, Task.managed_by_rule_id.is_(None)).one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    def _get_run(self, task_id: int, run_id: int) -> TaskJobRun:
        run = (
            self.db.query(TaskJobRun)
            .options(joinedload(TaskJobRun.task))
            .filter(TaskJobRun.id == run_id, TaskJobRun.task_id == task_id)
            .one_or_none()
        )
        if run is None:
            raise HTTPException(status_code=404, detail="Job run not found")
        return run

    @staticmethod
    def _to_run_summary(run: TaskJobRun) -> JobRunSummary:
        return JobRunSummary(
            id=run.id,
            name=run.job_name,
            namespace=run.namespace,
            taskId=run.task_id,
            taskName=run.task.name,
            releaseName=run.release_name,
            triggerType=run.trigger_type,
            status=run.status,
            startedAt=run.started_at,
            completedAt=run.completed_at,
            lastSeenAt=run.last_seen_at,
            hasLogs=bool(run.logs_text),
        )

    def _build_task_stats(self, task: Task, runs: list[TaskJobRun]) -> TaskJobStats:
        started_values = [run.started_at for run in runs if run.started_at is not None]
        completed_values = [run.completed_at for run in runs if run.completed_at is not None]

        return TaskJobStats(
            taskId=task.id,
            taskName=task.name,
            namespace=task.namespace,
            releaseName=task.release_name,
            totalRuns=len(runs),
            manualRuns=sum(1 for run in runs if run.trigger_type == "manual"),
            scheduledRuns=sum(1 for run in runs if run.trigger_type == "scheduled"),
            eventRuns=sum(1 for run in runs if run.trigger_type == "event"),
            succeededRuns=sum(1 for run in runs if run.status == "succeeded"),
            failedRuns=sum(1 for run in runs if run.status == "failed"),
            activeRuns=sum(1 for run in runs if run.status == "running"),
            unknownRuns=sum(1 for run in runs if run.status == "unknown"),
            lastStartedAt=max(started_values, default=None),
            lastCompletedAt=max(completed_values, default=None),
        )
