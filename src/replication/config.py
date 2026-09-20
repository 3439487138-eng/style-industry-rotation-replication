"""Portable configuration loading and production-readiness checks."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml

from .errors import ConfigurationError, ReplicationUnavailable


UNAVAILABLE_VALUES = {"", "unavailable", "none", "null", "todo"}
FORBIDDEN_PROVIDERS = {"demo", "fallback", "mock", "random", "synthetic", "toy"}
SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "tushare_token",
}


@dataclass(frozen=True)
class ProjectConfig:
    """Validated project configuration with resolved filesystem paths."""

    raw: dict[str, Any]
    project_root: Path
    config_path: Path
    adapter: str
    data_provider: str
    data_path: Path
    display_data_path: str
    output_directory: Path
    payload_path: Path
    report_path: Path
    required_env: tuple[str, ...]


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"'{name}' must be a YAML mapping.")
    return dict(value)


def _reject_embedded_secrets(value: Any, prefix: str = "") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            location = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in SENSITIVE_KEYS and child not in (None, ""):
                raise ConfigurationError(
                    f"Sensitive value is not allowed in config: {location}. "
                    "Use an environment variable named in data.required_env."
                )
            _reject_embedded_secrets(child, location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_embedded_secrets(child, f"{prefix}[{index}]")


def _parse_date(value: Any, name: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ConfigurationError(f"'{name}' must use YYYY-MM-DD format.") from exc


def _resolve(path_value: str | Path, project_root: Path) -> Path:
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def _require_inside_project(path: Path, root: Path, name: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ConfigurationError(f"'{name}' must stay inside the project directory.") from exc


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _validate_ready(config: ProjectConfig) -> None:
    adapter = config.adapter.strip().lower()
    provider = config.data_provider.strip().lower()
    if adapter in UNAVAILABLE_VALUES:
        raise ReplicationUnavailable(
            "No complete strategy implementation is present. Configure "
            "strategy.adapter as an importable 'module:function' only after supplying "
            "the original strategy engine."
        )
    if ":" not in config.adapter:
        raise ConfigurationError("strategy.adapter must use 'module:function' syntax.")
    if provider in UNAVAILABLE_VALUES:
        raise ReplicationUnavailable(
            "No authorized production data provider is configured. Set data.provider, "
            "data.path, and any required environment variables."
        )
    if provider in FORBIDDEN_PROVIDERS:
        raise ConfigurationError(
            f"data.provider '{config.data_provider}' is prohibited for replication output."
        )

    missing_env = [name for name in config.required_env if not os.getenv(name)]
    if missing_env:
        raise ReplicationUnavailable(
            "Required credentials/environment variables are missing: "
            + ", ".join(missing_env)
        )

    if provider == "local_files":
        if not config.data_path.exists():
            raise ReplicationUnavailable(
                f"Configured data path does not exist: {config.display_data_path}"
            )
        if config.data_path.is_dir() and not any(config.data_path.iterdir()):
            raise ReplicationUnavailable(
                f"Configured data directory is empty: {config.display_data_path}"
            )


def load_project_config(
    config_path: Path,
    project_root: Path,
    data_path_override: Path | None = None,
    adapter_override: str | None = None,
    *,
    require_ready: bool = False,
) -> ProjectConfig:
    """Load config with CLI > environment > YAML precedence."""

    root = project_root.resolve()
    source = config_path.resolve()
    if not source.is_file():
        raise ConfigurationError(f"Configuration file not found: {source}")
    try:
        loaded = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot read YAML configuration: {exc}") from exc
    raw = _mapping(loaded, "root")
    _reject_embedded_secrets(raw)

    strategy = _mapping(raw.get("strategy", {}), "strategy")
    data = _mapping(raw.get("data", {}), "data")
    outputs = _mapping(raw.get("outputs", {}), "outputs")

    start = _parse_date(raw.get("sample_start"), "sample_start")
    end = _parse_date(raw.get("sample_end"), "sample_end")
    if start > end:
        raise ConfigurationError("sample_start must not be later than sample_end.")

    configured_adapter = str(strategy.get("adapter", "unavailable")).strip()
    adapter = (
        adapter_override
        or os.getenv("REPLICATION_STRATEGY_ADAPTER")
        or configured_adapter
    ).strip()

    configured_data = data.get("path", "data/input")
    env_data = os.getenv("REPLICATION_DATA_PATH")
    selected_data: str | Path = data_path_override or env_data or configured_data
    data_path = _resolve(selected_data, root)

    required_env_value = data.get("required_env", [])
    if not isinstance(required_env_value, list) or not all(
        isinstance(item, str) and item.strip() for item in required_env_value
    ):
        raise ConfigurationError("data.required_env must be a list of environment names.")
    required_env = tuple(item.strip() for item in required_env_value)

    output_directory = _resolve(outputs.get("directory", "outputs"), root)
    payload_path = _resolve(outputs.get("payload", "outputs/report.json"), root)
    report_path = _resolve(outputs.get("report", "outputs/report.html"), root)
    _require_inside_project(output_directory, root, "outputs.directory")
    _require_inside_project(payload_path, root, "outputs.payload")
    _require_inside_project(report_path, root, "outputs.report")

    project = ProjectConfig(
        raw=raw,
        project_root=root,
        config_path=source,
        adapter=adapter,
        data_provider=str(data.get("provider", "unavailable")).strip(),
        data_path=data_path,
        display_data_path=_display_path(data_path, root),
        output_directory=output_directory,
        payload_path=payload_path,
        report_path=report_path,
        required_env=required_env,
    )
    if require_ready:
        _validate_ready(project)
    return project
