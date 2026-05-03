import json
import logging
import os
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import yaml


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [env-backupper] %(message)s",
)
logger = logging.getLogger(__name__)

RESOURCE_EXPORTS: list[tuple[str, str]] = [
    ("deployments.apps", "deployments.yaml"),
    ("statefulsets.apps", "statefulsets.yaml"),
    ("daemonsets.apps", "daemonsets.yaml"),
    ("cronjobs.batch", "cronjobs.yaml"),
    ("services", "services.yaml"),
    ("configmaps", "configmaps.yaml"),
    ("secrets", "secrets.yaml"),
    ("persistentvolumeclaims", "persistentvolumeclaims.yaml"),
    ("serviceaccounts", "serviceaccounts.yaml"),
    ("roles.rbac.authorization.k8s.io", "roles.yaml"),
    ("rolebindings.rbac.authorization.k8s.io", "rolebindings.yaml"),
    ("ingresses.networking.k8s.io", "ingresses.yaml"),
    ("networkpolicies.networking.k8s.io", "networkpolicies.yaml"),
    ("horizontalpodautoscalers.autoscaling", "horizontalpodautoscalers.yaml"),
]

EXCLUDED_SECRET_TYPES = {
    "helm.sh/release.v1",
    "kubernetes.io/service-account-token",
}


def main() -> None:
    namespace = require_env("TARGET_NAMESPACE")
    prefix = require_env("ENV_BACKUPS_FILENAME_PREFIX")
    bucket_name = require_env("DESTINATION_ENV_AWS_BUCKET_NAME")
    archive_name = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')}.backup.tgz"

    s3 = boto3.client(
        "s3",
        aws_access_key_id=require_env("DESTINATION_ENV_AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=require_env("DESTINATION_ENV_AWS_SECRET_ACCESS_KEY"),
        endpoint_url=require_env("DESTINATION_ENV_AWS_ENDPOINT"),
    )

    with tempfile.TemporaryDirectory(prefix="env-backup-") as temp_dir:
        root = Path(temp_dir)
        snapshot_dir = root / "snapshot"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        summary = export_namespace(namespace, snapshot_dir)
        metadata_path = snapshot_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "namespace": namespace,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "resources": summary,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        archive_path = root / archive_name
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(snapshot_dir, arcname=namespace)

        logger.info("Uploading namespace archive %s to bucket %s", archive_name, bucket_name)
        s3.upload_file(str(archive_path), bucket_name, archive_name)
        logger.info("Namespace backup uploaded successfully")


def export_namespace(namespace: str, snapshot_dir: Path) -> dict[str, int]:
    summary: dict[str, int] = {}

    for resource_name, filename in RESOURCE_EXPORTS:
        sanitized = sanitize_manifest(run_kubectl_get(resource_name, namespace))
        count = resource_count(sanitized)
        summary[resource_name] = count
        if count == 0:
            continue

        target = snapshot_dir / filename
        target.write_text(yaml.safe_dump(sanitized, sort_keys=False, allow_unicode=True), encoding="utf-8")
        logger.info("Exported %s resources for %s into %s", count, resource_name, filename)

    return summary


def run_kubectl_get(resource_name: str, namespace: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "kubectl",
            "get",
            resource_name,
            "-n",
            namespace,
            "-o",
            "yaml",
            "--ignore-not-found",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or f"kubectl get {resource_name} failed"
        raise RuntimeError(message)

    payload = yaml.safe_load(completed.stdout) or {}
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected kubectl payload for {resource_name}")
    return payload


def sanitize_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    kind = payload.get("kind")
    if kind == "List":
        items = []
        for item in payload.get("items", []) or []:
            sanitized = sanitize_resource(item)
            if sanitized is not None:
                items.append(sanitized)
        payload["items"] = items
        payload.pop("metadata", None)
        return payload

    sanitized = sanitize_resource(payload)
    return sanitized or {"apiVersion": "v1", "kind": "List", "items": []}


def sanitize_resource(resource: Any) -> dict[str, Any] | None:
    if not isinstance(resource, dict):
        return None

    if resource.get("kind") == "Secret" and resource.get("type") in EXCLUDED_SECRET_TYPES:
        return None

    metadata = resource.get("metadata")
    if isinstance(metadata, dict):
        for field in ("creationTimestamp", "generation", "managedFields", "resourceVersion", "selfLink", "uid"):
            metadata.pop(field, None)
        annotations = metadata.get("annotations")
        if isinstance(annotations, dict):
            annotations.pop("kubectl.kubernetes.io/last-applied-configuration", None)
            if not annotations:
                metadata.pop("annotations", None)

    resource.pop("status", None)

    if resource.get("kind") == "Service":
        spec = resource.get("spec")
        if isinstance(spec, dict):
            for field in ("clusterIP", "clusterIPs", "healthCheckNodePort", "ipFamilies", "ipFamilyPolicy"):
                spec.pop(field, None)

    return resource


def resource_count(payload: dict[str, Any]) -> int:
    if payload.get("kind") == "List":
        return len(payload.get("items", []) or [])
    return 1 if payload else 0


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


if __name__ == "__main__":
    main()
