from pathlib import Path

import pytest

from app.core.helm import HelmClient, HelmError


def test_helm_uses_local_chart_path_when_repository_url_is_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chart_dir = tmp_path / "chart"
    chart_dir.mkdir()

    run_calls: list[list[str]] = []

    def fake_run(command: list[str]) -> str:
        run_calls.append(command)
        return "ok"

    monkeypatch.setattr(HelmClient, "_run", staticmethod(fake_run))

    client = HelmClient(chart_repository_url="", chart_ref="master", chart_path=str(chart_dir))
    client.upgrade_install("release", "default", {"key": "value"})

    assert len(run_calls) == 1
    assert run_calls[0][:4] == ["helm", "upgrade", "--install", "release"]
    assert run_calls[0][4] == str(chart_dir)


def test_helm_raises_when_local_chart_path_is_missing(tmp_path: Path) -> None:
    client = HelmClient(chart_repository_url="", chart_ref="master", chart_path=str(tmp_path / "missing"))

    with pytest.raises(HelmError, match="Backup chart path not found"):
        client.upgrade_install("release", "default", {"key": "value"})
