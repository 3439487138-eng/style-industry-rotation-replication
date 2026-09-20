"""Validate configuration and production readiness without a traceback."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from replication.config import load_project_config  # noqa: E402
from replication.errors import ReplicationError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/base.yaml"))
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--adapter")
    parser.add_argument(
        "--structure-only",
        action="store_true",
        help="Validate YAML shape and portable paths without requiring private inputs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = args.config if args.config.is_absolute() else ROOT / args.config
    try:
        project = load_project_config(
            config_path=path,
            project_root=ROOT,
            data_path_override=args.data_path,
            adapter_override=args.adapter,
            require_ready=not args.structure_only,
        )
    except ReplicationError as exc:
        print(f"{exc.label}: {exc}", file=sys.stderr)
        return exc.exit_code
    print("VALID: configuration structure" if args.structure_only else f"READY: {project.adapter}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
