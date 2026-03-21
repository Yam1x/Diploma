from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.api.deps import get_minio_browser_service, get_task_service
from app.db import Base
from app.services.task_service import TaskService


class FakeHelm:
    def __init__(self) -> None:
        self.upgrade_calls: list[dict] = []
        self.uninstall_calls: list[tuple[str, str]] = []
        self.status_messages: dict[tuple[str, str], str] = {}

    def upgrade_install(
        self,
        release_name: str,
        namespace: str,
        values: dict,
        chart_repository_url: str | None = None,
        chart_ref: str | None = None,
        chart_path: str | None = None,
    ) -> str:
        self.upgrade_calls.append(
            {
                "release_name": release_name,
                "namespace": namespace,
                "values": values,
                "chart_repository_url": chart_repository_url,
                "chart_ref": chart_ref,
                "chart_path": chart_path,
            }
        )
        return "Release applied"

    def uninstall(self, release_name: str, namespace: str) -> str:
        self.uninstall_calls.append((release_name, namespace))
        return "Release removed"

    def status(self, release_name: str, namespace: str) -> str:
        return self.status_messages.get((release_name, namespace), f"status for {release_name}")


class FakeKube:
    def __init__(self) -> None:
        self.namespaces = {"default", "backups"}
        self.services = {
            "default": [
                {"name": "minio", "ports": [{"name": "api", "port": 9000}, {"name": "console", "port": 9001}]},
                {"name": "postgresql", "ports": [{"name": "postgresql", "port": 5432}]},
                {"name": "secure-s3", "ports": [{"name": "https", "port": 443}]},
            ],
            "backups": [],
        }

    def list_namespaces(self) -> list[str]:
        return sorted(self.namespaces)

    def list_services(self, namespace: str) -> list[dict]:
        return list(self.services.get(namespace, []))

    def create_namespace(self, namespace: str) -> str:
        if namespace in self.namespaces:
            raise RuntimeError(f"Namespace {namespace} already exists")
        self.namespaces.add(namespace)
        self.services.setdefault(namespace, [])
        return namespace

    def namespace_exists(self, namespace: str) -> bool:
        return namespace in self.namespaces


class FakeMinioBrowserService:
    def list_objects(self, prefix: str = "") -> dict:
        return {
            "bucketName": "backups",
            "prefix": prefix,
            "objects": [
                {
                    "key": f"{prefix}db/2026-03-21.dump" if prefix else "db/2026-03-21.dump",
                    "size": 4096,
                    "lastModified": datetime(2026, 3, 21, 8, 30, tzinfo=timezone.utc).isoformat(),
                    "etag": "etag-1",
                },
                {
                    "key": f"{prefix}s3/2026-03-21.tar.gz" if prefix else "s3/2026-03-21.tar.gz",
                    "size": 8192,
                    "lastModified": datetime(2026, 3, 21, 9, 0, tzinfo=timezone.utc).isoformat(),
                    "etag": "etag-2",
                },
            ],
        }


@pytest.fixture
def fake_helm() -> FakeHelm:
    return FakeHelm()


@pytest.fixture
def fake_kube() -> FakeKube:
    return FakeKube()


@pytest.fixture
def fake_minio_browser_service() -> FakeMinioBrowserService:
    return FakeMinioBrowserService()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def service(db_session: Session, fake_helm: FakeHelm, fake_kube: FakeKube) -> TaskService:
    return TaskService(db=db_session, helm=fake_helm, kube=fake_kube)


@pytest.fixture
def client(
    db_session: Session,
    fake_helm: FakeHelm,
    fake_kube: FakeKube,
    fake_minio_browser_service: FakeMinioBrowserService,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(main_module, "init_db", lambda: None)

    def override_get_task_service() -> TaskService:
        return TaskService(db=db_session, helm=fake_helm, kube=fake_kube)

    main_module.app.dependency_overrides[get_task_service] = override_get_task_service
    main_module.app.dependency_overrides[get_minio_browser_service] = lambda: fake_minio_browser_service
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()
