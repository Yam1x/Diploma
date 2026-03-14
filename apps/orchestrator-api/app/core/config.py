from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/orchestrator"
    backup_image_registry: str = "ghcr.io"
    backup_image_repository: str = "Yam1x/diploma-db-backupper"
    backup_image_tag: str = "latest"
    backup_image_pull_policy: str = "Always"
    backup_chart_repository_url: str = "https://github.com/Yam1x/Diploma.git"
    backup_chart_ref: str = "master"
    backup_chart_path: str = "diploma-db-backupper/ci"


@lru_cache
def get_settings() -> Settings:
    return Settings()
