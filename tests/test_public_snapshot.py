from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "public_index_snapshot"
CONVERTER = ROOT / "tools" / "prepare_open_index_data.py"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_fixed_public_snapshot_converts_to_manifest_locked_inputs(tmp_path: Path) -> None:
    output = tmp_path / "input"
    result = subprocess.run(
        [
            sys.executable,
            str(CONVERTER),
            "--source-dir",
            str(SNAPSHOT),
            "--manifest",
            str(SNAPSHOT / "manifest.json"),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    manifest = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))
    prices = pd.read_csv(output / "prices.csv", dtype={"asset": str})
    benchmark = pd.read_csv(output / "benchmark.csv")
    assert len(prices) == manifest["transformed"]["prices.csv"]["rows"]
    assert len(benchmark) == manifest["transformed"]["benchmark.csv"]["rows"]
    assert prices["asset"].nunique() == 6
    assert _sha256(output / "prices.csv") == manifest["transformed"]["prices.csv"]["sha256"]
    assert _sha256(output / "benchmark.csv") == manifest["transformed"]["benchmark.csv"]["sha256"]


def test_fixed_public_snapshot_rejects_tampering(tmp_path: Path) -> None:
    copied = tmp_path / "snapshot"
    shutil.copytree(SNAPSHOT, copied)
    with (copied / "sh000016.csv").open("ab") as handle:
        handle.write(b"\n")

    result = subprocess.run(
        [
            sys.executable,
            str(CONVERTER),
            "--source-dir",
            str(copied),
            "--manifest",
            str(copied / "manifest.json"),
            "--output-dir",
            str(tmp_path / "input"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "SHA-256 mismatch for sh000016.csv" in result.stderr


def test_full_workflow_runs_formal_entrypoint_and_validators() -> None:
    workflow = (ROOT / ".github" / "workflows" / "paper-replication.yml").read_text(
        encoding="utf-8"
    )
    assert "workflow_dispatch:" in workflow
    assert "tools/prepare_open_index_data.py" in workflow
    assert "python run_replication.py --config" in workflow
    assert "tools/validate_backtest.py" in workflow
    assert "outputs/performance_metrics.csv" in workflow
    assert "outputs/nav_curve.csv" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "continue-on-error" not in workflow
    assert "REPLICATION_DATA_ARCHIVE" not in workflow
