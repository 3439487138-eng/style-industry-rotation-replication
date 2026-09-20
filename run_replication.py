"""Run the configured strategy adapter and build an auditable HTML report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from replication.adapter import RunContext, execute_adapter, load_adapter  # noqa: E402
from replication.config import load_project_config  # noqa: E402
from replication.errors import ReplicationError  # noqa: E402
from replication.report import render_report, validate_payload, write_payload  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/base.yaml"))
    parser.add_argument(
        "--data-path",
        type=Path,
        help="Override data.path (also supported through REPLICATION_DATA_PATH).",
    )
    parser.add_argument(
        "--adapter",
        help="Override strategy.adapter as module:function "
        "(also supported through REPLICATION_STRATEGY_ADAPTER).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate production readiness without running the strategy.",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    project = load_project_config(
        config_path=config_path,
        project_root=ROOT,
        data_path_override=args.data_path,
        adapter_override=args.adapter,
        require_ready=True,
    )
    if args.check:
        print(
            "READY: configuration, data inputs, credentials, and strategy adapter "
            "are available."
        )
        return 0

    context = RunContext(
        project_root=ROOT,
        config_path=config_path.resolve(),
        data_path=project.data_path,
        output_directory=project.output_directory,
    )
    adapter = load_adapter(project.adapter)
    payload = execute_adapter(adapter, project, context)

    # Validate adapter evidence before adding orchestration metadata. This keeps
    # malformed private adapters on the stable REPORT_ERROR path.
    validate_payload(payload)

    run_metadata = payload["run"]
    run_metadata["generated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        displayed_config = config_path.relative_to(ROOT).as_posix()
    except ValueError:
        displayed_config = config_path.name
    run_metadata["command"] = f"python run_replication.py --config {displayed_config}"
    run_metadata["adapter"] = project.adapter
    run_metadata["data_provider"] = project.data_provider
    run_metadata["data_path"] = project.display_data_path
    write_payload(payload, project.payload_path)
    render_report(payload, project.report_path, ROOT)
    print(
        json.dumps(
            {
                "status": payload["run"]["status"],
                "payload": project.payload_path.relative_to(ROOT).as_posix(),
                "report": project.report_path.relative_to(ROOT).as_posix(),
            },
            ensure_ascii=False,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env")
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except ReplicationError as exc:
        print(f"{exc.label}: {exc}", file=sys.stderr)
        return exc.exit_code
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
