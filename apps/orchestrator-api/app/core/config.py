from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/orchestrator"

    db_backupper_image_registry: str = "ghcr.io"
    db_backupper_image_repository: str = "yam1x/diploma-db-backupper"
    db_backupper_image_tag: str = "latest"
    db_backupper_image_pull_policy: str = "Always"
    db_backupper_chart_repository_url: str = "https://github.com/Yam1x/Diploma.git"
    db_backupper_chart_ref: str = "master"
    db_backupper_chart_path: str = "diploma-db-backupper/ci"

    s3_backupper_image_registry: str = "ghcr.io"
    s3_backupper_image_repository: str = "yam1x/diploma-s3-backupper"
    s3_backupper_image_tag: str = "latest"
    s3_backupper_image_pull_policy: str = "Always"
    s3_backupper_chart_repository_url: str = "https://github.com/Yam1x/Diploma.git"
    s3_backupper_chart_ref: str = "master"
    s3_backupper_chart_path: str = "diploma-s3-backupper/ci"

    env_synchronizer_image_registry: str = "ghcr.io"
    env_synchronizer_image_repository: str = "yam1x/diploma-env-synchronizer"
    env_synchronizer_image_tag: str = "latest"
    env_synchronizer_image_pull_policy: str = "Always"
    env_synchronizer_chart_repository_url: str = "https://github.com/Yam1x/Diploma.git"
    env_synchronizer_chart_ref: str = "master"
    env_synchronizer_chart_path: str = "diploma-env-synchronizer/ci"

    minio_endpoint_url: str = "http://minio:9000"
    minio_access_key_id: str = "admin"
    minio_secret_access_key: str = "minio123456"
    minio_bucket_name: str = "backups"
    minio_region: str = "us-east-1"
    event_watcher_enabled: bool = False
    event_watcher_poll_interval_seconds: int = 60
    event_watcher_cooldown_seconds: int = 600


@lru_cache
def get_settings() -> Settings:
    return Settings()
