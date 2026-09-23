from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from replication.config import load_project_config
from replication.errors import ConfigurationError, ReplicationUnavailable


ROOT = Path(__file__).resolve().parents[1]


def test_default_config_has_real_adapter_but_fails_on_missing_data() -> None:
    config_path = ROOT / "config" / "base.yaml"
    project = load_project_config(config_path, ROOT)
    assert project.adapter == "strategy.adapter:run_strategy"
    assert project.display_data_path == "data/input"
    with pytest.raises(ReplicationUnavailable, match="prices.csv.*benchmark.csv"):
        load_project_config(config_path, ROOT, require_ready=True)


def _write_config(path: Path, **data_changes: object) -> None:
    payload = {
        "sample_start": "2020-01-01",
        "sample_end": "2020-12-31",
        "strategy": {"adapter": "package.module:run"},
        "data": {"provider": "local_files", "path": "input", "required_env": []},
        "outputs": {
            "directory": "outputs",
            "payload": "outputs/report.json",
            "report": "outputs/report.html",
        },
    }
    payload["data"].update(data_changes)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def test_missing_local_data_and_credentials_are_clear(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config.yaml"
    _write_config(config, required_env=["PRIVATE_DATA_TOKEN"])
    monkeypatch.delenv("PRIVATE_DATA_TOKEN", raising=False)
    with pytest.raises(ReplicationUnavailable, match="PRIVATE_DATA_TOKEN"):
        load_project_config(config, tmp_path, require_ready=True)
    monkeypatch.setenv("PRIVATE_DATA_TOKEN", "test-only")
    with pytest.raises(ReplicationUnavailable, match="does not exist"):
        load_project_config(config, tmp_path, require_ready=True)


def test_cli_path_overrides_environment_and_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config.yaml"
    _write_config(config)
    env_path = tmp_path / "env-input"
    cli_path = tmp_path / "cli input 中文"
    cli_path.mkdir()
    (cli_path / "real.csv").write_text("date,value\n2020-01-01,1\n", encoding="utf-8")
    monkeypatch.setenv("REPLICATION_DATA_PATH", str(env_path))
    project = load_project_config(config, tmp_path, data_path_override=cli_path, require_ready=True)
    assert project.data_path == cli_path.resolve()


def test_adapter_cli_override_precedes_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config.yaml"
    _write_config(config)
    monkeypatch.setenv("REPLICATION_STRATEGY_ADAPTER", "environment.module:run")
    project = load_project_config(
        config,
        tmp_path,
        adapter_override="command_line.module:run",
    )
    assert project.adapter == "command_line.module:run"


def test_output_paths_cannot_escape_repository(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    _write_config(config)
    payload = yaml.safe_load(config.read_text(encoding="utf-8"))
    payload["outputs"]["report"] = "../report.html"
    config.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="inside the project"):
        load_project_config(config, tmp_path)


def test_embedded_secret_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    _write_config(config, token="not-a-real-secret")
    with pytest.raises(ConfigurationError, match="Sensitive value"):
        load_project_config(config, tmp_path)


def test_synthetic_provider_is_prohibited(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    _write_config(config, provider="synthetic")
    with pytest.raises(ConfigurationError, match="prohibited"):
        load_project_config(config, tmp_path, require_ready=True)
