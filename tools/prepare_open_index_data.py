"""Convert the audited public-index snapshots into ignored production inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


SYMBOLS = {
    "sh000016": "SSE 50",
    "sh000300": "CSI 300",
    "sh000688": "STAR 50",
    "sh000852": "CSI 1000",
    "sh000905": "CSI 500",
    "sz399006": "ChiNext",
}
REQUIRED_SOURCE_COLUMNS = {"date", "close", "volume", "symbol", "source"}
BENCHMARK = "sh000300"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Snapshot manifest; defaults to <source-dir>/manifest.json when present",
    )
    parser.add_argument("--output-dir", default=Path("data/input"), type=Path)
    return parser.parse_args()


def sha256(path: Path, *, canonical_text: bool = False) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            if canonical_text:
                chunk = chunk.replace(b"\r\n", b"\n")
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        raise ValueError(f"Snapshot manifest is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("snapshot_id") != "china-equity-indices-2018-2026-v1":
        raise ValueError("Unexpected public snapshot identifier")
    return payload


def read_symbol(
    source_dir: Path,
    symbol: str,
    name: str,
    manifest: dict[str, Any] | None = None,
) -> pd.DataFrame:
    path = source_dir / f"{symbol}.csv"
    if not path.is_file():
        raise ValueError(f"Missing source file: {path}")
    expected = manifest.get("files", {}).get(path.name) if manifest else None
    if manifest and not expected:
        raise ValueError(f"Snapshot manifest has no entry for {path.name}")
    if expected and sha256(path, canonical_text=True) != expected.get("sha256"):
        raise ValueError(f"SHA-256 mismatch for {path.name}")
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_SOURCE_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path.name} is missing columns: {', '.join(missing)}")
    frame = frame.loc[:, ["date", "close", "volume", "symbol", "source"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    if frame[["date", "close", "volume", "symbol", "source"]].isna().any().any():
        raise ValueError(f"{path.name} contains missing or invalid required observations")
    if not frame["symbol"].astype(str).eq(symbol).all():
        raise ValueError(f"{path.name} contains an unexpected symbol")
    if (frame["close"] <= 0).any() or (frame["volume"] < 0).any():
        raise ValueError(f"{path.name} contains invalid close or volume values")
    if frame["date"].duplicated().any():
        raise ValueError(f"{path.name} contains duplicate dates")
    if not frame["source"].str.contains("AkShare", case=False, na=False).all():
        raise ValueError(f"{path.name} has an unrecognized source label")
    if expected:
        actual_start = frame["date"].min().date().isoformat()
        actual_end = frame["date"].max().date().isoformat()
        if len(frame) != int(expected["rows"]):
            raise ValueError(f"Row-count mismatch for {path.name}")
        if actual_start != expected["start_date"] or actual_end != expected["end_date"]:
            raise ValueError(f"Date-range mismatch for {path.name}")
    frame["asset"] = symbol
    frame["asset_name"] = name
    frame["asset_type"] = "equity_index"
    return frame.sort_values("date")


def main() -> int:
    args = parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    manifest_path = args.manifest.resolve() if args.manifest else source_dir / "manifest.json"
    manifest = load_manifest(manifest_path if manifest_path.exists() or args.manifest else None)
    panels = [
        read_symbol(source_dir, symbol, name, manifest)
        for symbol, name in SYMBOLS.items()
    ]
    prices = pd.concat(panels, ignore_index=True)
    prices = prices[
        ["date", "asset", "asset_name", "close", "volume", "asset_type", "source"]
    ].sort_values(["asset", "date"])
    benchmark = prices.loc[
        prices["asset"].eq(BENCHMARK), ["date", "close", "source"]
    ].copy()
    if benchmark.empty:
        raise ValueError(f"Benchmark {BENCHMARK} is absent")
    output_dir.mkdir(parents=True, exist_ok=True)
    prices_path = output_dir / "prices.csv"
    benchmark_path = output_dir / "benchmark.csv"
    prices.to_csv(
        prices_path, index=False, encoding="utf-8-sig", lineterminator="\n"
    )
    benchmark.to_csv(
        benchmark_path, index=False, encoding="utf-8-sig", lineterminator="\n"
    )
    if manifest:
        transformed = manifest.get("transformed", {})
        prices_spec = transformed.get("prices.csv", {})
        benchmark_spec = transformed.get("benchmark.csv", {})
        expected_prices = prices_spec.get("sha256")
        expected_benchmark = benchmark_spec.get("sha256")
        if len(prices) != int(prices_spec.get("rows", -1)):
            raise ValueError("Transformed prices.csv row-count mismatch")
        if len(benchmark) != int(benchmark_spec.get("rows", -1)):
            raise ValueError("Transformed benchmark.csv row-count mismatch")
        if expected_prices and sha256(prices_path) != expected_prices:
            raise ValueError("Transformed prices.csv SHA-256 mismatch")
        if expected_benchmark and sha256(benchmark_path) != expected_benchmark:
            raise ValueError("Transformed benchmark.csv SHA-256 mismatch")
    print(
        f"WROTE: {len(prices)} price rows, {prices['asset'].nunique()} indices, "
        f"{prices['date'].min().date()} to {prices['date'].max().date()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
