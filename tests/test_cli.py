from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_default_entrypoint_exits_cleanly_without_traceback() -> None:
    result = subprocess.run(
        [sys.executable, "run_replication.py", "--check"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert result.returncode == 3
    assert result.stderr.startswith("UNAVAILABLE:")
    assert "Traceback" not in result.stderr
