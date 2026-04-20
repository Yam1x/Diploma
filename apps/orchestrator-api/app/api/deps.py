from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.event_rule_service import EventRuleService
from app.services.minio_browser_service import MinioBrowserService
from app.services.notification_service import NotificationService
from app.services.stats_service import StatsService
from app.services.task_service import TaskService


def get_task_service(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db=db)


def get_event_rule_service(db: Session = Depends(get_db)) -> EventRuleService:
    return EventRuleService(db=db)


def get_minio_browser_service() -> MinioBrowserService:
    return MinioBrowserService()


def get_stats_service(db: Session = Depends(get_db)) -> StatsService:
    return StatsService(db=db)


def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(db=db)
