"""Download and safely extract an authorized private data ZIP for Actions."""

from __future__ import annotations

import argparse
import os
import urllib.request
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = os.getenv("REPLICATION_DATA_ARCHIVE_URL")
    token = os.getenv("REPLICATION_DATA_ARCHIVE_TOKEN")
    if not url:
        print("ERROR: missing REPLICATION_DATA_ARCHIVE_URL")
        return 2
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    archive = args.output.parent / "private-data.zip"
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            archive.write_bytes(response.read())
        with zipfile.ZipFile(archive) as bundle:
            root = args.output.resolve()
            for member in bundle.infolist():
                target = (root / member.filename).resolve()
                try:
                    target.relative_to(root)
                except ValueError as exc:
                    raise RuntimeError("Private data archive contains an unsafe path") from exc
            bundle.extractall(root)
    finally:
        archive.unlink(missing_ok=True)
    print("PRIVATE_DATA_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
