from __future__ import annotations

from pathlib import Path

import pytest

from replication.errors import ReportError
from replication.report import load_payload, render_report, validate_payload, write_payload


def valid_payload() -> dict[str, object]:
    return {
        "paper": {"title": "Fixture <paper>", "citation": "test", "source": "test"},
        "run": {
            "status": "adapted",
            "mode": "test",
            "sample": "2020",
            "generated_at": "now",
            "commit_sha": "test",
            "command": "test",
        },
        "summary": "Test fixture only; never a strategy result.",
        "metrics": [{"Metric": "Fixture", "Baseline": "unavailable"}],
        "methodology": [
            {"Paper rule": "Fixture", "Implementation": "Fixture", "Status": "adapted"}
        ],
        "assumptions": ["fixture"],
        "fidelity_gaps": ["fixture"],
        "figures": [],
        "tables": [],
    }


def test_payload_roundtrip_and_standalone_report(tmp_path: Path) -> None:
    payload_path = tmp_path / "outputs" / "report.json"
    report_path = tmp_path / "outputs" / "report.html"
    payload = valid_payload()
    write_payload(payload, payload_path)
    render_report(load_payload(payload_path), report_path, tmp_path)
    document = report_path.read_text(encoding="utf-8")
    assert "Figures and Result Tables" in document
    assert "Fixture &lt;paper&gt;" in document
    assert "Fixture <paper>" not in document


def test_report_rejects_missing_fields_and_invalid_status() -> None:
    payload = valid_payload()
    del payload["metrics"]
    with pytest.raises(ReportError, match="missing keys"):
        validate_payload(payload)
    payload = valid_payload()
    methodology = payload["methodology"]
    assert isinstance(methodology, list)
    methodology[0]["Status"] = "complete"
    with pytest.raises(ReportError, match="controlled vocabulary"):
        validate_payload(payload)
