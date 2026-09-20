from __future__ import annotations

import sys
import types
from pathlib import Path

from replication.adapter import RunContext, execute_adapter, load_adapter
from replication.config import ProjectConfig


def test_adapter_is_loaded_and_called_once(tmp_path: Path) -> None:
    calls: list[tuple[ProjectConfig, RunContext]] = []
    module = types.ModuleType("test_strategy_adapter")

    def run(config: ProjectConfig, context: RunContext) -> dict[str, object]:
        calls.append((config, context))
        return {"source": "test fixture only"}

    module.run = run  # type: ignore[attr-defined]
    sys.modules[module.__name__] = module
    try:
        config = ProjectConfig(
            raw={},
            project_root=tmp_path,
            config_path=tmp_path / "config.yaml",
            adapter="test_strategy_adapter:run",
            data_provider="local_files",
            data_path=tmp_path,
            display_data_path=".",
            output_directory=tmp_path / "outputs",
            payload_path=tmp_path / "outputs/report.json",
            report_path=tmp_path / "outputs/report.html",
            required_env=(),
        )
        context = RunContext(tmp_path, config.config_path, tmp_path, config.output_directory)
        result = execute_adapter(load_adapter(config.adapter), config, context)
    finally:
        sys.modules.pop(module.__name__, None)
    assert result == {"source": "test fixture only"}
    assert calls == [(config, context)]
