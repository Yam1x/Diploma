from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


NotificationSeverity = Literal["info", "success", "warning", "error"]


class NotificationItem(BaseModel):
    id: int
    kind: str
    severity: NotificationSeverity
    title: str
    message: str
    taskId: int | None
    jobRunId: int | None
    linkPath: str | None
    isRead: bool
    readAt: datetime | None
    createdAt: datetime


class NotificationsResponse(BaseModel):
    unreadCount: int
    items: list[NotificationItem]
