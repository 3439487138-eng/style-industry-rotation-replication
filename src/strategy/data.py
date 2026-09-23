"""Load real market observations and enforce the strategy data contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from replication.config import ProjectConfig
from replication.errors import ReplicationUnavailable


STOCK_PANEL_COLUMNS = {
    "date",
    "asset",
    "close",
    "turnover",
    "market_cap",
    "industry",
    "asset_type",
}
INDEX_PROXY_COLUMNS = {"date", "asset", "close", "volume", "asset_type", "source"}
BENCHMARK_COLUMNS = {"date", "close"}


@dataclass(frozen=True)
class MarketData:
    prices: pd.DataFrame
    benchmark: pd.DataFrame
    prices_path: Path
    benchmark_path: Path
    profile: str = "stock_panel"


def normalize_asset_code(value: object) -> str:
    code = str(value).strip().upper()
    code = code.replace(".XSHE", ".SZ").replace(".XSHG", ".SH")
    if code.endswith("XSHE") and "." not in code:
        code = code[:-4] + ".SZ"
    elif code.endswith("XSHG") and "." not in code:
        code = code[:-4] + ".SH"
    return code


def _read_csv(path: Path, required: set[str], label: str) -> pd.DataFrame:
    if not path.is_file():
        raise ReplicationUnavailable(f"Required {label} file is missing: {path.name}")
    try:
        frame = pd.read_csv(path)
    except (OSError, UnicodeError, pd.errors.ParserError) as exc:
        raise ReplicationUnavailable(f"Cannot read {label} file '{path.name}': {exc}") from exc
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ReplicationUnavailable(
            f"{label} file '{path.name}' is missing columns: {', '.join(missing)}"
        )
    if frame.empty:
        raise ReplicationUnavailable(f"{label} file '{path.name}' contains no observations")
    return frame


def _parse_dates(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    if result["date"].isna().any():
        raise ReplicationUnavailable(f"{label} contains invalid dates")
    return result


def load_market_data(config: ProjectConfig) -> MarketData:
    data_config = config.raw.get("data", {})
    profile = str(data_config.get("profile", "stock_panel")).lower()
    if profile not in {"stock_panel", "public_index_proxy"}:
        raise ReplicationUnavailable(
            "data.profile must be 'stock_panel' or 'public_index_proxy'"
        )
    price_columns = (
        INDEX_PROXY_COLUMNS if profile == "public_index_proxy" else STOCK_PANEL_COLUMNS
    )
    prices_path = config.data_path / str(data_config.get("prices_file", "prices.csv"))
    benchmark_path = config.data_path / str(
        data_config.get("benchmark_file", "benchmark.csv")
    )
    prices = _parse_dates(_read_csv(prices_path, price_columns, "prices"), "prices")
    benchmark = _parse_dates(
        _read_csv(benchmark_path, BENCHMARK_COLUMNS, "benchmark"), "benchmark"
    )

    prices["asset"] = prices["asset"].map(normalize_asset_code)
    numeric_columns = ["close"]
    numeric_columns.extend(
        ["volume"] if profile == "public_index_proxy" else ["turnover", "market_cap"]
    )
    for column in numeric_columns:
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
    benchmark["close"] = pd.to_numeric(benchmark["close"], errors="coerce")

    if prices[numeric_columns].isna().any().any():
        raise ReplicationUnavailable("prices contains non-numeric or missing required values")
    if benchmark["close"].isna().any():
        raise ReplicationUnavailable("benchmark contains non-numeric or missing close values")
    if (prices["close"] <= 0).any() or (benchmark["close"] <= 0).any():
        raise ReplicationUnavailable("close values must be strictly positive")
    if profile == "stock_panel":
        if (prices["market_cap"] <= 0).any() or (prices["turnover"] < 0).any():
            raise ReplicationUnavailable("market_cap must be positive and turnover non-negative")
    elif (prices["volume"] < 0).any():
        raise ReplicationUnavailable("volume must be non-negative")
    if prices["asset"].eq("").any():
        raise ReplicationUnavailable("prices contains an empty asset code")
    categorical_columns = (
        ["asset_type", "source"]
        if profile == "public_index_proxy"
        else ["industry", "asset_type"]
    )
    if prices[categorical_columns].isna().any().any():
        raise ReplicationUnavailable(
            f"{', '.join(categorical_columns)} must be present for every row"
        )
    if prices.duplicated(["date", "asset"]).any():
        raise ReplicationUnavailable("prices contains duplicate date/asset observations")
    if benchmark.duplicated(["date"]).any():
        raise ReplicationUnavailable("benchmark contains duplicate dates")

    start = pd.Timestamp(config.raw["sample_start"])
    end = pd.Timestamp(config.raw["sample_end"])
    prices = prices.loc[prices["date"].between(start, end)].copy()
    benchmark = benchmark.loc[benchmark["date"].between(start, end)].copy()
    if prices.empty or benchmark.empty:
        raise ReplicationUnavailable("No observations remain inside the configured sample")

    prices = prices.sort_values(["asset", "date"]).reset_index(drop=True)
    benchmark = benchmark.sort_values("date").reset_index(drop=True)
    if not np.isfinite(prices[numeric_columns].to_numpy()).all():
        raise ReplicationUnavailable("prices contains non-finite values")
    if prices["date"].nunique() < 3:
        raise ReplicationUnavailable("At least three trading dates are required")
    if prices["date"].min() < benchmark["date"].min() or prices["date"].max() > benchmark["date"].max():
        raise ReplicationUnavailable("benchmark does not cover the full prices date range")

    return MarketData(prices, benchmark, prices_path, benchmark_path, profile)
