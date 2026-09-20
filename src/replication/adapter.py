"""Thin boundary between project orchestration and an original strategy engine."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import ProjectConfig
from .errors import AdapterError


@dataclass(frozen=True)
class RunContext:
    project_root: Path
    config_path: Path
    data_path: Path
    output_directory: Path


StrategyAdapter = Callable[[ProjectConfig, RunContext], dict[str, Any]]


def load_adapter(specification: str) -> StrategyAdapter:
    """Import a configured adapter without embedding strategy logic in the runner."""

    module_name, separator, function_name = specification.partition(":")
    if not separator or not module_name or not function_name:
        raise AdapterError("Adapter must use 'module:function' syntax.")
    try:
        module = importlib.import_module(module_name)
    except (ImportError, OSError) as exc:
        raise AdapterError(f"Cannot import adapter module '{module_name}': {exc}") from exc
    adapter = getattr(module, function_name, None)
    if not callable(adapter):
        raise AdapterError(
            f"Adapter function '{function_name}' is missing or not callable in '{module_name}'."
        )
    return adapter


def execute_adapter(
    adapter: StrategyAdapter, config: ProjectConfig, context: RunContext
) -> dict[str, Any]:
    """Execute the real adapter once and reject invalid or placeholder returns."""

    try:
        payload = adapter(config, context)
    except AdapterError:
        raise
    except Exception as exc:
        raise AdapterError(f"Strategy adapter failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise AdapterError("Strategy adapter must return a report payload dictionary.")
    return payload
