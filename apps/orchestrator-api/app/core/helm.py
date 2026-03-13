from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import yaml


class HelmError(RuntimeError):
    pass


class HelmClient:
    KUBECONFIG_PATH = "/app/config/kubeconfig"
    BACKUP_CHART_PATH = Path(__file__).resolve().parents[3] / "diploma-db-backupper" / "ci"

    def upgrade_install(self, release_name: str, namespace: str, values: dict) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as handle:
            yaml.safe_dump(values, handle, sort_keys=False)
            values_path = handle.name
        try:
            command = [
                "helm",
                "upgrade",
                "--install",
                release_name,
                str(self.BACKUP_CHART_PATH),
                "--namespace",
                namespace,
                "-f",
                values_path,
                "--kubeconfig",
                self.KUBECONFIG_PATH,
            ]
            return self._run(command)
        finally:
            Path(values_path).unlink(missing_ok=True)

    def uninstall(self, release_name: str, namespace: str) -> str:
        command = [
            "helm",
            "uninstall",
            release_name,
            "--namespace",
            namespace,
            "--kubeconfig",
            self.KUBECONFIG_PATH,
        ]
        return self._run(command)

    def status(self, release_name: str, namespace: str) -> str:
        command = [
            "helm",
            "status",
            release_name,
            "--namespace",
            namespace,
            "--kubeconfig",
            self.KUBECONFIG_PATH,
        ]
        return self._run(command)

    def _run(self, command: list[str]) -> str:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "Helm command failed"
            raise HelmError(message)
        return completed.stdout.strip()
