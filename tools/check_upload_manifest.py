"""Validate the explicit pre-Git upload candidate manifest."""

from __future__ import annotations

from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "upload-manifest.txt"
FORBIDDEN_PARTS = {
    ".git",
    ".pytest_cache",
    ".temp",
    ".venv",
    "__pycache__",
    "build",
    "cache",
    "db",
    "dist",
    "logs",
}
FORBIDDEN_SUFFIXES = {".db", ".log", ".pdf", ".pyc", ".sqlite", ".xlsx"}
REQUIRED_LEGACY = {
    ".github/workflows/paper-replication.yml",
    ".github/workflows/public-checks.yml",
    "data/public_index_snapshot/manifest.json",
    "data/public_index_snapshot/sh000016.csv",
    "data/public_index_snapshot/sh000300.csv",
    "data/public_index_snapshot/sh000688.csv",
    "data/public_index_snapshot/sh000852.csv",
    "data/public_index_snapshot/sh000905.csv",
    "data/public_index_snapshot/sz399006.csv",
    "panda_factor/LICENSE",
    "examples/style_industry_neutralize_demo.py",
    "panda_factor/panda_factor/panda_factor/analysis/alpha_calculator.py",
    "panda_factor/panda_factor/panda_factor/analysis/factor.py",
    "panda_factor/panda_factor/panda_factor/analysis/factor_func.py",
    "panda_factor/panda_factor/panda_factor/generate/factor_utils.py",
    "scripts/calculate_alpha.py",
    "src/strategy/adapter.py",
    "src/strategy/factors.py",
    "src/strategy/portfolio.py",
    "tools/clean_generated_outputs.py",
}


def load_manifest() -> list[str]:
    return [
        line.strip()
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def main() -> int:
    entries = load_manifest()
    errors: list[str] = []
    if len(entries) != len(set(entries)):
        errors.append("manifest contains duplicate entries")
    if entries != sorted(entries, key=str.casefold):
        errors.append("manifest entries are not case-insensitively sorted")
    missing_core = sorted(REQUIRED_LEGACY - set(entries))
    if missing_core:
        errors.append("required legacy source missing: " + ", ".join(missing_core))

    for entry in entries:
        pure = PurePosixPath(entry)
        if pure.is_absolute() or ".." in pure.parts:
            errors.append(f"unsafe path: {entry}")
            continue
        lowered_parts = {part.lower() for part in pure.parts}
        if lowered_parts & FORBIDDEN_PARTS:
            errors.append(f"forbidden generated/private path: {entry}")
        if pure.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden file type: {entry}")
        path = ROOT / entry
        if not path.is_file():
            errors.append(f"missing file: {entry}")
        elif path.stat().st_size > 5 * 1024 * 1024:
            errors.append(f"file exceeds 5 MiB: {entry}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"VALID: {len(entries)} upload candidates; core legacy source is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
