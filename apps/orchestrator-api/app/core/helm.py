from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import yaml

from app.core.config import get_settings


class HelmError(RuntimeError):
    pass


class HelmClient:
    def __init__(
        self,
        chart_repository_url: str | None = None,
        chart_ref: str | None = None,
        chart_path: str | None = None,
    ) -> None:
        settings = get_settings()
        self.chart_repository_url = chart_repository_url or settings.backup_chart_repository_url
        self.chart_ref = chart_ref or settings.backup_chart_ref
        self.chart_path = Path(chart_path or settings.backup_chart_path)

    def upgrade_install(self, release_name: str, namespace: str, values: dict) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as handle:
            yaml.safe_dump(values, handle, sort_keys=False)
            values_path = handle.name
        try:
            with tempfile.TemporaryDirectory() as checkout_dir:
                checkout_path = Path(checkout_dir)
                self._clone_chart_source(checkout_path)
                chart_path = checkout_path / self.chart_path
                if not chart_path.exists():
                    raise HelmError(f"Backup chart path not found: {chart_path}")
                command = [
                    "helm",
                    "upgrade",
                    "--install",
                    release_name,
                    str(chart_path),
                    "--namespace",
                    namespace,
                    "-f",
                    values_path,
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
        ]
        return self._run(command)

    def status(self, release_name: str, namespace: str) -> str:
        command = [
            "helm",
            "status",
            release_name,
            "--namespace",
            namespace,
        ]
        return self._run(command)

    def _run(self, command: list[str]) -> str:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "Command failed"
            raise HelmError(message)
        return completed.stdout.strip()

    def _clone_chart_source(self, checkout_path: Path) -> None:
        command = [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            self.chart_ref,
            self.chart_repository_url,
            str(checkout_path),
        ]
        self._run(command)
