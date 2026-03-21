from __future__ import annotations

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from app.core.config import Settings, get_settings
from app.schemas.minio import MinioObjectSummary, MinioObjectsResponse


class MinioBrowserService:
    def __init__(self, settings: Settings | None = None, client=None) -> None:
        self.settings = settings or get_settings()
        self.client = client or boto3.client(
            "s3",
            endpoint_url=self.settings.minio_endpoint_url,
            aws_access_key_id=self.settings.minio_access_key_id,
            aws_secret_access_key=self.settings.minio_secret_access_key,
            region_name=self.settings.minio_region,
            config=Config(signature_version="s3v4"),
        )

    def list_objects(self, prefix: str = "") -> MinioObjectsResponse:
        normalized_prefix = prefix.strip()

        try:
            response = self.client.list_objects_v2(
                Bucket=self.settings.minio_bucket_name,
                Prefix=normalized_prefix,
                MaxKeys=500,
            )
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(status_code=502, detail=f"Не удалось загрузить файлы MinIO: {exc}") from exc

        objects = [
            MinioObjectSummary(
                key=item["Key"],
                size=int(item.get("Size", 0)),
                lastModified=item.get("LastModified"),
                etag=(item.get("ETag") or "").strip('"') or None,
            )
            for item in response.get("Contents", [])
            if item.get("Key")
        ]

        return MinioObjectsResponse(
            bucketName=self.settings.minio_bucket_name,
            prefix=normalized_prefix,
            objects=objects,
        )
