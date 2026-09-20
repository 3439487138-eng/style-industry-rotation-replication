"""Scan GitHub candidate files without printing possible secret values."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "upload-manifest.txt"
PATTERNS = {
    "Windows absolute path": re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]") ,
    "macOS user path": re.compile(r"/" + r"Users/[^/\s]+/"),
    "credential assignment": re.compile(
        r"(?i)(?:api[_-]?key|authorization|cookie|password|secret|token)"
        r"\s*[=:]\s*(['\"])[A-Za-z0-9_./+\-=]{20,}\1"
    ),
}


def candidate_files() -> list[Path]:
    if not MANIFEST.is_file():
        raise RuntimeError(f"Upload manifest is missing: {MANIFEST}")
    relative_paths = [
        line.strip()
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return [ROOT / relative_path for relative_path in relative_paths]


def main() -> int:
    findings: list[tuple[str, int, str]] = []
    for path in candidate_files():
        if not path.is_file():
            findings.append((path.relative_to(ROOT).as_posix(), 0, "manifest file missing"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((path.relative_to(ROOT).as_posix(), line_number, name))
    if (ROOT / ".env").exists():
        findings.append((".env", 0, "local environment file"))
    if findings:
        for path, line, kind in findings:
            location = f"{path}:{line}" if line else path
            print(f"FOUND: {location} [{kind}]")
        return 1
    print(f"CLEAN: scanned {len(candidate_files())} GitHub candidate files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
