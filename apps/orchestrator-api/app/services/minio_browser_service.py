from __future__ import annotations

from collections.abc import Iterator
from pathlib import PurePosixPath

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

    def delete_object(self, key: str) -> None:
        normalized_key = self._normalize_key(key)

        try:
            self.client.delete_object(Bucket=self.settings.minio_bucket_name, Key=normalized_key)
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(status_code=502, detail=f"Не удалось удалить файл MinIO: {exc}") from exc

    def get_object_stream(self, key: str) -> tuple[Iterator[bytes], str, str]:
        normalized_key = self._normalize_key(key)

        try:
            response = self.client.get_object(Bucket=self.settings.minio_bucket_name, Key=normalized_key)
        except self.client.exceptions.NoSuchKey as exc:
            raise HTTPException(status_code=404, detail="Файл MinIO не найден") from exc
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(status_code=502, detail=f"Не удалось скачать файл MinIO: {exc}") from exc

        body = response["Body"]
        content_type = response.get("ContentType") or "application/octet-stream"
        filename = PurePosixPath(normalized_key).name or "download"
        return body.iter_chunks(), filename, content_type

    def get_usage_summary(self, prefix: str = "") -> dict[str, int]:
        normalized_prefix = prefix.strip()
        continuation_token: str | None = None
        object_count = 0
        total_size = 0

        try:
            while True:
                params = {
                    "Bucket": self.settings.minio_bucket_name,
                    "Prefix": normalized_prefix,
                    "MaxKeys": 1000,
                }
                if continuation_token:
                    params["ContinuationToken"] = continuation_token

                response = self.client.list_objects_v2(**params)
                for item in response.get("Contents", []):
                    if not item.get("Key"):
                        continue
                    object_count += 1
                    total_size += int(item.get("Size", 0) or 0)

                if not response.get("IsTruncated"):
                    break
                continuation_token = response.get("NextContinuationToken")
                if not continuation_token:
                    break
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(status_code=502, detail=f"Не удалось получить статистику MinIO: {exc}") from exc

        return {
            "objectCount": object_count,
            "totalSize": total_size,
        }

    @staticmethod
    def _normalize_key(key: str) -> str:
        normalized_key = key.strip()
        if not normalized_key:
            raise HTTPException(status_code=400, detail="Ключ файла MinIO не указан")
        return normalized_key
