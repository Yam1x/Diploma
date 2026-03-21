from fastapi import APIRouter, Depends, Query

from app.api.deps import get_minio_browser_service, get_task_service
from app.schemas.minio import MinioObjectsResponse
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
from app.services.task_service import TaskService


api_router = APIRouter()


@api_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


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


@api_router.get("/tasks", response_model=list[TaskSummary])
def list_tasks(service: TaskService = Depends(get_task_service)) -> list[TaskSummary]:
    return service.list_tasks()


@api_router.post("/tasks", response_model=TaskDetail, status_code=201)
def create_task(payload: TaskCreate, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.create_task(payload)


@api_router.get("/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: int, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.get_task(task_id)


@api_router.patch("/tasks/{task_id}", response_model=TaskDetail)
def update_task(task_id: int, payload: TaskUpdate, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.update_task(task_id, payload)


@api_router.post("/tasks/{task_id}/enable", response_model=TaskDetail)
def enable_task(task_id: int, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.enable_task(task_id)


@api_router.post("/tasks/{task_id}/disable", response_model=TaskDetail)
def disable_task(task_id: int, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.disable_task(task_id)


@api_router.post("/tasks/{task_id}/refresh", response_model=TaskDetail)
def refresh_task(task_id: int, service: TaskService = Depends(get_task_service)) -> TaskDetail:
    return service.refresh_task(task_id)


@api_router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, service: TaskService = Depends(get_task_service)) -> None:
    service.delete_task(task_id)
