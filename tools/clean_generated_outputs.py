"""Remove only known generated outputs before proving full regeneration."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


GENERATED = (
    "backtest_report.md",
    "factor_effectiveness.csv",
    "figures",
    "monthly_returns.csv",
    "nav_curve.csv",
    "performance_metrics.csv",
    "positions.csv",
    "report.html",
    "report.json",
    "rotation_signals.csv",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", type=Path, default=Path("outputs"))
    return parser.parse_args()


def main() -> int:
    output = parse_args().outputs.resolve()
    removed: list[str] = []
    for relative in GENERATED:
        target = (output / relative).resolve()
        target.relative_to(output)
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(relative)
        elif target.exists():
            target.unlink()
            removed.append(relative)
    print(f"REMOVED: {len(removed)} generated paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
