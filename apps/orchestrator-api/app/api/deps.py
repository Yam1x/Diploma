from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.minio_browser_service import MinioBrowserService
from app.services.stats_service import StatsService
from app.services.task_service import TaskService


def get_task_service(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db=db)


def get_minio_browser_service() -> MinioBrowserService:
    return MinioBrowserService()


def get_stats_service(db: Session = Depends(get_db)) -> StatsService:
    return StatsService(db=db)
