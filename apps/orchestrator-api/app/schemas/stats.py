from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class StorageStats(BaseModel):
    bucketName: str
    objectCount: int
    totalSize: int


class JobRunSummary(BaseModel):
    name: str
    namespace: str
    taskId: int
    taskName: str
    releaseName: str
    triggerType: Literal["manual", "scheduled"]
    status: Literal["running", "succeeded", "failed", "unknown"]
    startedAt: datetime | None
    completedAt: datetime | None


class TaskJobStats(BaseModel):
    taskId: int
    taskName: str
    namespace: str
    releaseName: str
    totalRuns: int
    manualRuns: int
    scheduledRuns: int
    succeededRuns: int
    failedRuns: int
    activeRuns: int
    unknownRuns: int
    lastStartedAt: datetime | None
    lastCompletedAt: datetime | None


class JobsStats(BaseModel):
    totalRuns: int
    manualRuns: int
    scheduledRuns: int
    succeededRuns: int
    failedRuns: int
    activeRuns: int
    unknownRuns: int
    recentRuns: list[JobRunSummary]
    tasks: list[TaskJobStats]


class DashboardStatsResponse(BaseModel):
    storage: StorageStats
    jobs: JobsStats
