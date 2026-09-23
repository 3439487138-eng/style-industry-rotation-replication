"""Convert the audited public-index snapshots into ignored production inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

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
    parser.add_argument("--output-dir", default=Path("data/input"), type=Path)
    return parser.parse_args()


def read_symbol(source_dir: Path, symbol: str, name: str) -> pd.DataFrame:
    path = source_dir / f"{symbol}.csv"
    if not path.is_file():
        raise ValueError(f"Missing source file: {path}")
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
    frame["asset"] = symbol
    frame["asset_name"] = name
    frame["asset_type"] = "equity_index"
    return frame.sort_values("date")


def main() -> int:
    args = parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    panels = [read_symbol(source_dir, symbol, name) for symbol, name in SYMBOLS.items()]
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
    prices.to_csv(output_dir / "prices.csv", index=False, encoding="utf-8-sig")
    benchmark.to_csv(output_dir / "benchmark.csv", index=False, encoding="utf-8-sig")
    print(
        f"WROTE: {len(prices)} price rows, {prices['asset'].nunique()} indices, "
        f"{prices['date'].min().date()} to {prices['date'].max().date()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
