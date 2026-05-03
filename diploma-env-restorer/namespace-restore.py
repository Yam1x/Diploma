import json
import logging
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path

import boto3


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [env-restorer] %(message)s",
)
logger = logging.getLogger(__name__)

RESTORE_ORDER = [
    "serviceaccounts.yaml",
    "roles.yaml",
    "rolebindings.yaml",
    "configmaps.yaml",
    "secrets.yaml",
    "services.yaml",
    "persistentvolumeclaims.yaml",
    "deployments.yaml",
    "statefulsets.yaml",
    "daemonsets.yaml",
    "cronjobs.yaml",
    "ingresses.yaml",
    "networkpolicies.yaml",
    "horizontalpodautoscalers.yaml",
]


def main() -> None:
    namespace = require_env("TARGET_NAMESPACE")
    prefix = require_env("ENV_BACKUPS_FILENAME_PREFIX")
    bucket_name = require_env("SOURCE_ENV_AWS_BUCKET_NAME")

    s3 = boto3.client(
        "s3",
        aws_access_key_id=require_env("SOURCE_ENV_AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=require_env("SOURCE_ENV_AWS_SECRET_ACCESS_KEY"),
        endpoint_url=require_env("SOURCE_ENV_AWS_ENDPOINT"),
    )

    backup_key = resolve_latest_backup_key(s3, bucket_name, prefix)
    logger.info("Selected backup %s from bucket %s", backup_key, bucket_name)

    with tempfile.TemporaryDirectory(prefix="env-restore-") as temp_dir:
        root = Path(temp_dir)
        archive_path = root / "restore.backup.tgz"
        extract_dir = root / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        s3.download_file(bucket_name, backup_key, str(archive_path))
        logger.info("Downloaded archive to %s", archive_path)

        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(extract_dir)

        snapshot_dir = resolve_snapshot_dir(extract_dir)
        validate_snapshot_namespace(snapshot_dir, namespace)
        restore_snapshot(snapshot_dir, namespace)

    logger.info("Environment restore finished")


def resolve_latest_backup_key(s3, bucket_name: str, prefix: str) -> str:
    continuation_token = None
    matching_keys: list[str] = []

    while True:
        params = {"Bucket": bucket_name, "MaxKeys": 1000}
        if prefix:
            params["Prefix"] = prefix
        if continuation_token:
            params["ContinuationToken"] = continuation_token

        response = s3.list_objects_v2(**params)
        for item in response.get("Contents", []):
            key = str(item.get("Key", ""))
            if key.endswith(".backup.tgz") and key.startswith(prefix):
                matching_keys.append(key)

        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")
        if not continuation_token:
            break

    if not matching_keys:
        raise RuntimeError(f"No backup archives found in bucket {bucket_name} for prefix '{prefix}'")

    return max(matching_keys)


def resolve_snapshot_dir(extract_dir: Path) -> Path:
    metadata_files = list(extract_dir.glob("**/metadata.json"))
    if not metadata_files:
        raise RuntimeError("Backup archive does not contain metadata.json")
    if len(metadata_files) > 1:
        raise RuntimeError("Backup archive contains multiple metadata.json files")
    return metadata_files[0].parent


def validate_snapshot_namespace(snapshot_dir: Path, target_namespace: str) -> None:
    metadata_path = snapshot_dir / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Backup metadata is invalid: {exc}") from exc

    archive_namespace = str(metadata.get("namespace", "")).strip()
    if not archive_namespace:
        raise RuntimeError("Backup metadata does not contain namespace")
    if archive_namespace != target_namespace:
        raise RuntimeError(
            f"Backup namespace '{archive_namespace}' does not match target namespace '{target_namespace}'"
        )


def restore_snapshot(snapshot_dir: Path, namespace: str) -> None:
    for filename in RESTORE_ORDER:
        manifest_path = snapshot_dir / filename
        if not manifest_path.exists():
            logger.info("Skipping %s because it is absent in the backup", filename)
            continue
        logger.info("Applying %s into namespace %s", filename, namespace)
        apply_manifest(manifest_path, namespace)


def apply_manifest(manifest_path: Path, namespace: str) -> None:
    completed = subprocess.run(
        [
            "kubectl",
            "apply",
            "-n",
            namespace,
            "-f",
            str(manifest_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or f"kubectl apply failed for {manifest_path.name}"
        raise RuntimeError(message)
    if completed.stdout.strip():
        logger.info(completed.stdout.strip())


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


if __name__ == "__main__":
    main()
