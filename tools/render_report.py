"""Render a standalone HTML report from a current-run JSON payload."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from replication.errors import ReplicationError  # noqa: E402
from replication.report import load_payload, render_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, default=Path("outputs/report.json"))
    parser.add_argument("--report", type=Path, default=Path("outputs/report.html"))
    args = parser.parse_args(argv)
    payload_path = args.payload if args.payload.is_absolute() else ROOT / args.payload
    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    try:
        render_report(load_payload(payload_path), report_path, ROOT)
    except ReplicationError as exc:
        print(f"{exc.label}: {exc}", file=sys.stderr)
        return exc.exit_code
    print(f"WROTE: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
