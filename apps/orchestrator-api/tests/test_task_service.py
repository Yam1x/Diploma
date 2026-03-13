from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.task_service import TaskService


class FakeHelm:
    def upgrade_install(self, release_name: str, namespace: str, values: dict) -> str:
        return "ok"

    def uninstall(self, release_name: str, namespace: str) -> str:
        return "removed"

    def status(self, release_name: str, namespace: str) -> str:
        return "deployed"


class FakeKube:
    def list_namespaces(self) -> list[str]:
        return ["default", "backup"]

    def namespace_exists(self, namespace: str) -> bool:
        return namespace in self.list_namespaces()


def make_service() -> TaskService:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    return TaskService(session, helm=FakeHelm(), kube=FakeKube())


def task_payload(enabled: bool = False) -> TaskCreate:
    return TaskCreate(
        name="Primary DB",
        namespace="default",
        enabled=enabled,
        schedule="0 * * * *",
        dbBackupsFilenamePrefix="backup",
        databaseHost="postgres",
        databaseName="app",
        databaseUsername="app",
        databasePassword="secret",
        destinationAwsEndpoint="https://s3.local",
        destinationAwsBucketName="bucket",
        destinationAwsAccessKeyId="key",
        destinationAwsSecretAccessKey="secret-key",
    )


def test_create_disabled_task_does_not_apply_release() -> None:
    service = make_service()

    result = service.create_task(task_payload(enabled=False))

    assert result.enabled is False
    assert result.lastApplyStatus is None


def test_create_enabled_task_applies_release() -> None:
    service = make_service()

    result = service.create_task(task_payload(enabled=True))

    assert result.enabled is True
    assert result.lastApplyStatus == "deployed"
    assert result.releaseName == "db-backupper-1"


def test_patch_secret_empty_value_clears_secret() -> None:
    service = make_service()
    task = service.create_task(task_payload(enabled=False))

    updated = service.update_task(task.id, TaskUpdate(databasePassword=""))

    assert updated.hasDatabasePassword is False


def test_disable_triggers_uninstall() -> None:
    service = make_service()
    created = service.create_task(task_payload(enabled=True))

    disabled = service.disable_task(created.id)

    assert disabled.enabled is False
    assert disabled.lastApplyStatus == "disabled"


def test_refresh_updates_status_snapshot() -> None:
    service = make_service()
    created = service.create_task(task_payload(enabled=False))

    refreshed = service.refresh_task(created.id)

    assert refreshed.lastApplyStatus == "deployed"
