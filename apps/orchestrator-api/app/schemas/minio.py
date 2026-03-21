from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MinioObjectSummary(BaseModel):
    key: str
    size: int
    lastModified: datetime | None
    etag: str | None


class MinioObjectsResponse(BaseModel):
    bucketName: str
    prefix: str
    objects: list[MinioObjectSummary]
