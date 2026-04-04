from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from typing import Any


class KubernetesError(RuntimeError):
    pass


class KubeClient:
    SYSTEM_NAMESPACES = {
        "default",
        "kube-node-lease",
        "kube-public",
        "kube-system",
        "local-path-storage",
    }

    def list_namespaces(self) -> list[str]:
        command = [
            "kubectl",
            "get",
            "namespaces",
            "-o",
            "json",
        ]
        output = self._run(command)
        payload = json.loads(output)
        return [
            item["metadata"]["name"]
            for item in payload.get("items", [])
            if item["metadata"]["name"] not in self.SYSTEM_NAMESPACES
        ]

    def list_services(self, namespace: str) -> list[dict[str, Any]]:
        command = [
            "kubectl",
            "get",
            "services",
            "-n",
            namespace,
            "-o",
            "json",
        ]
        output = self._run(command)
        payload = json.loads(output)
        services: list[dict[str, Any]] = []

        for item in payload.get("items", []):
            metadata = item.get("metadata", {})
            spec = item.get("spec", {})
            name = metadata.get("name")
            if not name:
                continue

            ports: list[dict[str, Any]] = []
            for port in spec.get("ports", []):
                value = port.get("port")
                if not isinstance(value, int):
                    continue
                ports.append(
                    {
                        "name": port.get("name"),
                        "port": value,
                    }
                )

            services.append(
                {
                    "name": name,
                    "ports": ports,
                }
            )

        return sorted(services, key=lambda service: str(service["name"]))

    def create_job_from_cronjob(self, namespace: str, cronjob_name: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%m%d%H%M%S")
        prefix = cronjob_name[: 63 - len("-manual-") - len(timestamp)]
        job_name = f"{prefix}-manual-{timestamp}"
        command = [
            "kubectl",
            "create",
            "job",
            job_name,
            f"--from=cronjob/{cronjob_name}",
            "-n",
            namespace,
            "-o",
            "json",
        ]
        output = self._run(command)
        payload = json.loads(output)
        return payload["metadata"]["name"]

    def namespace_exists(self, namespace: str) -> bool:
        return namespace in self.list_namespaces()

    def create_namespace(self, namespace: str) -> str:
        command = [
            "kubectl",
            "create",
            "namespace",
            namespace,
            "-o",
            "json",
        ]
        output = self._run(command)
        payload = json.loads(output)
        return payload["metadata"]["name"]

    def list_jobs(self, namespace: str) -> list[dict[str, Any]]:
        command = [
            "kubectl",
            "get",
            "jobs",
            "-n",
            namespace,
            "-o",
            "json",
        ]
        output = self._run(command)
        payload = json.loads(output)
        jobs: list[dict[str, Any]] = []

        for item in payload.get("items", []):
            metadata = item.get("metadata", {})
            status = item.get("status", {})
            name = metadata.get("name")
            if not name:
                continue

            jobs.append(
                {
                    "name": name,
                    "namespace": namespace,
                    "active": int(status.get("active", 0) or 0),
                    "succeeded": int(status.get("succeeded", 0) or 0),
                    "failed": int(status.get("failed", 0) or 0),
                    "startTime": self._parse_datetime(status.get("startTime")),
                    "completionTime": self._parse_datetime(status.get("completionTime")),
                }
            )

        jobs.sort(
            key=lambda job: (
                job["startTime"] or job["completionTime"] or datetime.fromtimestamp(0, tz=timezone.utc),
                job["name"],
            ),
            reverse=True,
        )
        return jobs

    def _run(self, command: list[str]) -> str:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "Kubernetes command failed"
            raise KubernetesError(message)
        return completed.stdout

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None

        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
