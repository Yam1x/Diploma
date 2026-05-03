from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("namespace-restore.py")
SPEC = importlib.util.spec_from_file_location("namespace_restore", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
namespace_restore = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(namespace_restore)


def build_archive(snapshot_namespace: str, files: dict[str, str] | None = None) -> bytes:
    buffer = io.BytesIO()
    payloads = {
        "metadata.json": json.dumps({"namespace": snapshot_namespace, "resources": {}}),
        **(files or {}),
    }

    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in payloads.items():
            encoded = content.encode("utf-8")
            info = tarfile.TarInfo(name=f"{snapshot_namespace}/{name}")
            info.size = len(encoded)
            archive.addfile(info, io.BytesIO(encoded))

    return buffer.getvalue()


class FakeS3:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def list_objects_v2(self, **params):
        prefix = params.get("Prefix", "")
        contents = [{"Key": key} for key in sorted(self.objects) if key.startswith(prefix)]
        return {"Contents": contents, "IsTruncated": False}

    def download_file(self, bucket_name: str, key: str, target_path: str) -> None:
        Path(target_path).write_bytes(self.objects[key])


def test_resolve_latest_backup_key_picks_latest_match() -> None:
    s3 = FakeS3(
        {
            "namespace-default-2026-05-01T01-00-00Z.backup.tgz": b"a",
            "namespace-default-2026-05-02T01-00-00Z.backup.tgz": b"b",
            "other-2026-05-03T01-00-00Z.backup.tgz": b"c",
        }
    )

    key = namespace_restore.resolve_latest_backup_key(s3, "backups", "namespace-default")

    assert key == "namespace-default-2026-05-02T01-00-00Z.backup.tgz"


def test_validate_snapshot_namespace_rejects_mismatch(tmp_path: Path) -> None:
    archive_path = tmp_path / "restore.backup.tgz"
    archive_path.write_bytes(build_archive("source"))
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()

    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(extract_dir)

    snapshot_dir = namespace_restore.resolve_snapshot_dir(extract_dir)

    with pytest.raises(RuntimeError, match="does not match target namespace"):
        namespace_restore.validate_snapshot_namespace(snapshot_dir, "target")


def test_restore_snapshot_applies_known_files_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot_dir = tmp_path / "default"
    snapshot_dir.mkdir()
    (snapshot_dir / "metadata.json").write_text(json.dumps({"namespace": "default"}), encoding="utf-8")
    (snapshot_dir / "configmaps.yaml").write_text("kind: List\nitems: []\n", encoding="utf-8")
    (snapshot_dir / "deployments.yaml").write_text("kind: List\nitems: []\n", encoding="utf-8")
    (snapshot_dir / "services.yaml").write_text("kind: List\nitems: []\n", encoding="utf-8")

    applied: list[str] = []

    def fake_apply(manifest_path: Path, namespace: str) -> None:
        assert namespace == "default"
        applied.append(manifest_path.name)

    monkeypatch.setattr(namespace_restore, "apply_manifest", fake_apply)

    namespace_restore.restore_snapshot(snapshot_dir, "default")

    assert applied == ["configmaps.yaml", "services.yaml", "deployments.yaml"]
