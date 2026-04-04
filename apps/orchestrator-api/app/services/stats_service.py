from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.kube import KubeClient, KubernetesError
from app.models.task import Task
from app.schemas.stats import DashboardStatsResponse, JobRunSummary, JobsStats, StorageStats, TaskJobStats
from app.services.minio_browser_service import MinioBrowserService


@dataclass(frozen=True)
class _MatchedJob:
    task_id: int
    task_name: str
    release_name: str
    namespace: str
    name: str
    trigger_type: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None


class StatsService:
    def __init__(
        self,
        db: Session,
        kube: KubeClient | None = None,
        minio: MinioBrowserService | None = None,
    ) -> None:
        self.db = db
        self.kube = kube or KubeClient()
        self.minio = minio or MinioBrowserService()
        self.settings = get_settings()

    def get_dashboard_stats(self) -> DashboardStatsResponse:
        tasks = self.db.query(Task).order_by(Task.name.asc()).all()
        storage_summary = self.minio.get_usage_summary()
        storage = StorageStats(
            bucketName=self.settings.minio_bucket_name,
            objectCount=storage_summary["objectCount"],
            totalSize=storage_summary["totalSize"],
        )

        jobs_by_namespace = self._load_jobs_by_namespace(tasks)
        matched_jobs: list[_MatchedJob] = []
        task_stats: list[TaskJobStats] = []

        for task in tasks:
            release_jobs = self._match_jobs(task, jobs_by_namespace.get(task.namespace, []))
            task_stats.append(self._build_task_stats(task, release_jobs))
            matched_jobs.extend(release_jobs)

        recent_runs = [
            JobRunSummary(
                name=job.name,
                namespace=job.namespace,
                taskId=job.task_id,
                taskName=job.task_name,
                releaseName=job.release_name,
                triggerType=job.trigger_type,
                status=job.status,
                startedAt=job.started_at,
                completedAt=job.completed_at,
            )
            for job in sorted(
                matched_jobs,
                key=lambda item: (
                    item.started_at or item.completed_at or datetime.fromtimestamp(0, tz=timezone.utc),
                    item.name,
                ),
                reverse=True,
            )[:10]
        ]

        jobs = JobsStats(
            totalRuns=len(matched_jobs),
            manualRuns=sum(1 for job in matched_jobs if job.trigger_type == "manual"),
            scheduledRuns=sum(1 for job in matched_jobs if job.trigger_type == "scheduled"),
            succeededRuns=sum(1 for job in matched_jobs if job.status == "succeeded"),
            failedRuns=sum(1 for job in matched_jobs if job.status == "failed"),
            activeRuns=sum(1 for job in matched_jobs if job.status == "running"),
            unknownRuns=sum(1 for job in matched_jobs if job.status == "unknown"),
            recentRuns=recent_runs,
            tasks=task_stats,
        )

        return DashboardStatsResponse(storage=storage, jobs=jobs)

    def _load_jobs_by_namespace(self, tasks: list[Task]) -> dict[str, list[dict]]:
        namespaces = sorted({task.namespace for task in tasks if task.release_name})
        jobs_by_namespace: dict[str, list[dict]] = {}

        for namespace in namespaces:
            try:
                jobs_by_namespace[namespace] = self.kube.list_jobs(namespace)
            except KubernetesError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        return jobs_by_namespace

    def _match_jobs(self, task: Task, jobs: list[dict]) -> list[_MatchedJob]:
        release_name = task.release_name
        if not release_name:
            return []

        matched: list[_MatchedJob] = []
        manual_prefix = f"{release_name}-manual-"
        scheduled_prefix = f"{release_name}-"

        for job in jobs:
            job_name = str(job.get("name", ""))
            if not job_name.startswith(scheduled_prefix):
                continue

            trigger_type = "manual" if job_name.startswith(manual_prefix) else "scheduled"
            matched.append(
                _MatchedJob(
                    task_id=task.id,
                    task_name=task.name,
                    release_name=release_name,
                    namespace=task.namespace,
                    name=job_name,
                    trigger_type=trigger_type,
                    status=self._resolve_job_status(job),
                    started_at=job.get("startTime"),
                    completed_at=job.get("completionTime"),
                )
            )

        return matched

    @staticmethod
    def _resolve_job_status(job: dict) -> str:
        if int(job.get("active", 0) or 0) > 0:
            return "running"
        if int(job.get("succeeded", 0) or 0) > 0:
            return "succeeded"
        if int(job.get("failed", 0) or 0) > 0:
            return "failed"
        return "unknown"

    def _build_task_stats(self, task: Task, jobs: list[_MatchedJob]) -> TaskJobStats:
        started_values = [job.started_at for job in jobs if job.started_at is not None]
        completed_values = [job.completed_at for job in jobs if job.completed_at is not None]

        return TaskJobStats(
            taskId=task.id,
            taskName=task.name,
            namespace=task.namespace,
            releaseName=task.release_name,
            totalRuns=len(jobs),
            manualRuns=sum(1 for job in jobs if job.trigger_type == "manual"),
            scheduledRuns=sum(1 for job in jobs if job.trigger_type == "scheduled"),
            succeededRuns=sum(1 for job in jobs if job.status == "succeeded"),
            failedRuns=sum(1 for job in jobs if job.status == "failed"),
            activeRuns=sum(1 for job in jobs if job.status == "running"),
            unknownRuns=sum(1 for job in jobs if job.status == "unknown"),
            lastStartedAt=max(started_values, default=None),
            lastCompletedAt=max(completed_values, default=None),
        )
