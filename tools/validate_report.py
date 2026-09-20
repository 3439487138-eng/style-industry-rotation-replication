"""Validate the JSON evidence contract and standalone HTML structure."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from replication.errors import ReportError  # noqa: E402
from replication.report import load_payload  # noqa: E402


REQUIRED_HEADINGS = (
    "Executive Summary",
    "Headline Metrics",
    "Figures and Result Tables",
    "Methodology Mapping",
    "Data and Assumptions",
    "Fidelity Gaps and Limitations",
    "Reproducibility",
)


def validate_html(path: Path) -> None:
    try:
        document = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReportError(f"HTML report not found: {path}") from exc
    except (OSError, UnicodeError) as exc:
        raise ReportError(f"Cannot read HTML report '{path}': {exc}") from exc
    missing = [heading for heading in REQUIRED_HEADINGS if heading not in document]
    if missing:
        raise ReportError("HTML report is missing sections: " + ", ".join(missing))
    if "<html" not in document.lower() or "</html>" not in document.lower():
        raise ReportError("HTML report is not a complete document.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("outputs/report.html"))
    parser.add_argument("--payload", type=Path, default=Path("outputs/report.json"))
    args = parser.parse_args(argv)
    report = args.report if args.report.is_absolute() else ROOT / args.report
    payload = args.payload if args.payload.is_absolute() else ROOT / args.payload
    try:
        load_payload(payload)
        validate_html(report)
    except ReportError as exc:
        print(f"{exc.label}: {exc}", file=sys.stderr)
        return exc.exit_code
    print("VALID: report payload and HTML structure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
