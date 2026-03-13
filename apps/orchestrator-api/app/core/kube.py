from __future__ import annotations

import json
import subprocess


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

    def namespace_exists(self, namespace: str) -> bool:
        return namespace in self.list_namespaces()

    def _run(self, command: list[str]) -> str:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "Kubernetes command failed"
            raise KubernetesError(message)
        return completed.stdout
