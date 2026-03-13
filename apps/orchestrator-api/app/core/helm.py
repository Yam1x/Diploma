from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import yaml

from app.core.config import get_settings


class HelmError(RuntimeError):
    pass


class HelmClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def upgrade_install(self, release_name: str, namespace: str, values: dict) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as handle:
            yaml.safe_dump(values, handle, sort_keys=False)
            values_path = handle.name
        try:
            command = [
                self.settings.helm_binary,
                "upgrade",
                "--install",
                release_name,
                str(Path(self.settings.backup_chart_path)),
                "--namespace",
                namespace,
                "-f",
                values_path,
                "--kubeconfig",
                self.settings.kubeconfig,
            ]
            return self._run(command)
        finally:
            Path(values_path).unlink(missing_ok=True)

    def uninstall(self, release_name: str, namespace: str) -> str:
        command = [
            self.settings.helm_binary,
            "uninstall",
            release_name,
            "--namespace",
            namespace,
            "--kubeconfig",
            self.settings.kubeconfig,
        ]
        return self._run(command)

    def status(self, release_name: str, namespace: str) -> str:
        command = [
            self.settings.helm_binary,
            "status",
            release_name,
            "--namespace",
            namespace,
            "--kubeconfig",
            self.settings.kubeconfig,
        ]
        return self._run(command)

    def _run(self, command: list[str]) -> str:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "Helm command failed"
            raise HelmError(message)
        return completed.stdout.strip()
