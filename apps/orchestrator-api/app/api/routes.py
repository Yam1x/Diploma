from fastapi import APIRouter, Depends

from app.api.deps import get_task_service
from app.schemas.task import HealthResponse, NamespaceListResponse, TaskCreate, TaskDetail, TaskSummary, TaskUpdate
from app.services.task_service import TaskService


api_router = APIRouter()


@api_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@api_router.get("/namespaces", response_model=NamespaceListResponse)
def list_namespaces(service: TaskService = Depends(get_task_service)) -> NamespaceListResponse:
    return NamespaceListResponse(namespaces=service.list_namespaces())


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
