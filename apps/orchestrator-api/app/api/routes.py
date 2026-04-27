from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import (
    get_event_rule_service,
    get_minio_browser_service,
    get_notification_service,
    get_recovery_rule_service,
    get_stats_service,
    get_task_service,
)
from app.schemas.event_rule import BackupEventRuleCreate, BackupEventRuleDetail, BackupEventRuleSummary, BackupEventRuleUpdate
from app.schemas.minio import MinioObjectsResponse
from app.schemas.notification import NotificationsResponse
from app.schemas.recovery_rule import RecoveryEventRuleCreate, RecoveryEventRuleDetail, RecoveryEventRuleSummary, RecoveryEventRuleUpdate
from app.schemas.stats import DashboardStatsResponse, JobRunLogsResponse, TaskJobRunsResponse
from app.schemas.task import (
    HealthResponse,
    NamespaceCreateRequest,
    NamespaceListResponse,
    NamespaceResponse,
    ServiceDiscoveryResponse,
    TaskCreate,
    TaskDetail,
    TaskSummary,
    TaskUpdate,
)
from app.services.minio_browser_service import MinioBrowserService
from app.services.notification_service import NotificationService
from app.services.event_rule_service import EventRuleService
from app.services.recovery_rule_service import RecoveryEventRuleService
from app.services.stats_service import StatsService
from app.services.task_service import TaskService


api_router = APIRouter()


@api_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@api_router.get("/stats/overview", response_model=DashboardStatsResponse)
def get_dashboard_stats(service: StatsService = Depends(get_stats_service)) -> DashboardStatsResponse:
    return service.get_dashboard_stats()


@api_router.get("/notifications", response_model=NotificationsResponse)
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    unread_only: bool = Query(default=False, alias="unreadOnly"),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationsResponse:
    return service.list_notifications(limit=limit, unread_only=unread_only)


@api_router.post("/notifications/{notification_id}/read", status_code=204)
def mark_notification_read(
    notification_id: int,
    service: NotificationService = Depends(get_notification_service),
) -> None:
    service.mark_read(notification_id)


@api_router.post("/notifications/read-all", status_code=204)
def mark_all_notifications_read(service: NotificationService = Depends(get_notification_service)) -> None:
    service.mark_all_read()


@api_router.get("/namespaces", response_model=NamespaceListResponse)
def list_namespaces(service: TaskService = Depends(get_task_service)) -> NamespaceListResponse:
    return NamespaceListResponse(namespaces=service.list_namespaces())


@api_router.post("/namespaces", response_model=NamespaceResponse, status_code=201)
def create_namespace(payload: NamespaceCreateRequest, service: TaskService = Depends(get_task_service)) -> NamespaceResponse:
    return NamespaceResponse(name=service.create_namespace(payload.name))


@api_router.get("/namespaces/{namespace}/service-discovery", response_model=ServiceDiscoveryResponse)
def list_service_discovery(namespace: str, service: TaskService = Depends(get_task_service)) -> ServiceDiscoveryResponse:
    return service.list_service_discovery(namespace)


@api_router.get("/minio/objects", response_model=MinioObjectsResponse)
def list_minio_objects(
    prefix: str = Query(default="", max_length=255),
    service: MinioBrowserService = Depends(get_minio_browser_service),
) -> MinioObjectsResponse:
    return service.list_objects(prefix)


@api_router.get("/minio/objects/download")
def download_minio_object(
    key: str = Query(min_length=1, max_length=1024),
    service: MinioBrowserService = Depends(get_minio_browser_service),
) -> StreamingResponse:
    stream, filename, content_type = service.get_object_stream(key)
    return StreamingResponse(
        stream,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_router.delete("/minio/objects", status_code=204)
def delete_minio_object(
    key: str = Query(min_length=1, max_length=1024),
    service: MinioBrowserService = Depends(get_minio_browser_service),
) -> None:
    service.delete_object(key)


@api_router.get("/tasks", response_model=list[TaskSummary])
def list_tasks(service: TaskService = Depends(get_task_service)) -> list[TaskSummary]:
    return service.list_tasks()


@api_router.post("/tasks", response_model=TaskDetail, status_code=201)
def create_task(payload: TaskCreate, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.create_task(payload)


@api_router.get("/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: int, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.get_task(task_id)


@api_router.get("/tasks/{task_id}/job-runs", response_model=TaskJobRunsResponse)
def list_task_job_runs(task_id: int, service: StatsService = Depends(get_stats_service)) -> TaskJobRunsResponse:
    return service.list_task_job_runs(task_id)


@api_router.get("/tasks/{task_id}/job-runs/{run_id}/logs", response_model=JobRunLogsResponse)
def get_task_job_run_logs(task_id: int, run_id: int, service: StatsService = Depends(get_stats_service)) -> JobRunLogsResponse:
    return service.get_task_job_run_logs(task_id, run_id)


@api_router.patch("/tasks/{task_id}", response_model=TaskDetail)
def update_task(task_id: int, payload: TaskUpdate, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.update_task(task_id, payload)


@api_router.post("/tasks/{task_id}/enable", response_model=TaskDetail)
def enable_task(task_id: int, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.enable_task(task_id)


@api_router.post("/tasks/{task_id}/run", response_model=TaskDetail)
def run_task(task_id: int, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.run_task(task_id)


@api_router.post("/tasks/{task_id}/disable", response_model=TaskDetail)
def disable_task(task_id: int, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.disable_task(task_id)


@api_router.post("/tasks/{task_id}/refresh", response_model=TaskDetail)
def refresh_task(task_id: int, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.refresh_task(task_id)


@api_router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, service: TaskService = Depends(get_task_service)) -> None:
    service.delete_task(task_id)


@api_router.get("/event-rules", response_model=list[BackupEventRuleSummary])
def list_event_rules(service: EventRuleService = Depends(get_event_rule_service)) -> list[BackupEventRuleSummary]:
    return service.list_rules()


@api_router.post("/event-rules", response_model=BackupEventRuleDetail, status_code=201)
def create_event_rule(payload: BackupEventRuleCreate, service: EventRuleService = Depends(get_event_rule_service)) -> BackupEventRuleDetail:
    return service.create_rule(payload)


@api_router.get("/event-rules/{rule_id}", response_model=BackupEventRuleDetail)
def get_event_rule(rule_id: int, service: EventRuleService = Depends(get_event_rule_service)) -> BackupEventRuleDetail:
    return service.get_rule(rule_id)


@api_router.patch("/event-rules/{rule_id}", response_model=BackupEventRuleDetail)
def update_event_rule(
    rule_id: int,
    payload: BackupEventRuleUpdate,
    service: EventRuleService = Depends(get_event_rule_service),
) -> BackupEventRuleDetail:
    return service.update_rule(rule_id, payload)


@api_router.post("/event-rules/{rule_id}/enable", response_model=BackupEventRuleDetail)
def enable_event_rule(rule_id: int, service: EventRuleService = Depends(get_event_rule_service)) -> BackupEventRuleDetail:
    return service.enable_rule(rule_id)


@api_router.post("/event-rules/{rule_id}/run", response_model=BackupEventRuleDetail)
def run_event_rule(rule_id: int, service: EventRuleService = Depends(get_event_rule_service)) -> BackupEventRuleDetail:
    return service.run_rule(rule_id)


@api_router.post("/event-rules/{rule_id}/disable", response_model=BackupEventRuleDetail)
def disable_event_rule(rule_id: int, service: EventRuleService = Depends(get_event_rule_service)) -> BackupEventRuleDetail:
    return service.disable_rule(rule_id)


@api_router.delete("/event-rules/{rule_id}", status_code=204)
def delete_event_rule(rule_id: int, service: EventRuleService = Depends(get_event_rule_service)) -> None:
    service.delete_rule(rule_id)


@api_router.get("/recovery-rules", response_model=list[RecoveryEventRuleSummary])
def list_recovery_rules(service: RecoveryEventRuleService = Depends(get_recovery_rule_service)) -> list[RecoveryEventRuleSummary]:
    return service.list_rules()


@api_router.post("/recovery-rules", response_model=RecoveryEventRuleDetail, status_code=201)
def create_recovery_rule(payload: RecoveryEventRuleCreate, service: RecoveryEventRuleService = Depends(get_recovery_rule_service)) -> RecoveryEventRuleDetail:
    return service.create_rule(payload)


@api_router.get("/recovery-rules/{rule_id}", response_model=RecoveryEventRuleDetail)
def get_recovery_rule(rule_id: int, service: RecoveryEventRuleService = Depends(get_recovery_rule_service)) -> RecoveryEventRuleDetail:
    return service.get_rule(rule_id)


@api_router.patch("/recovery-rules/{rule_id}", response_model=RecoveryEventRuleDetail)
def update_recovery_rule(
    rule_id: int,
    payload: RecoveryEventRuleUpdate,
    service: RecoveryEventRuleService = Depends(get_recovery_rule_service),
) -> RecoveryEventRuleDetail:
    return service.update_rule(rule_id, payload)


@api_router.post("/recovery-rules/{rule_id}/enable", response_model=RecoveryEventRuleDetail)
def enable_recovery_rule(rule_id: int, service: RecoveryEventRuleService = Depends(get_recovery_rule_service)) -> RecoveryEventRuleDetail:
    return service.enable_rule(rule_id)


@api_router.post("/recovery-rules/{rule_id}/run", response_model=RecoveryEventRuleDetail)
def run_recovery_rule(rule_id: int, service: RecoveryEventRuleService = Depends(get_recovery_rule_service)) -> RecoveryEventRuleDetail:
    return service.run_rule(rule_id)


@api_router.post("/recovery-rules/{rule_id}/disable", response_model=RecoveryEventRuleDetail)
def disable_recovery_rule(rule_id: int, service: RecoveryEventRuleService = Depends(get_recovery_rule_service)) -> RecoveryEventRuleDetail:
    return service.disable_rule(rule_id)


@api_router.delete("/recovery-rules/{rule_id}", status_code=204)
def delete_recovery_rule(rule_id: int, service: RecoveryEventRuleService = Depends(get_recovery_rule_service)) -> None:
    service.delete_rule(rule_id)
