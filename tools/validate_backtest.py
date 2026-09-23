"""Cross-check current real-data backtest artifacts against inputs and formulas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


REQUIRED_OUTPUTS = {
    "performance_metrics.csv",
    "monthly_returns.csv",
    "nav_curve.csv",
    "positions.csv",
    "rotation_signals.csv",
    "backtest_report.md",
    "figures/nav_curve.png",
    "figures/drawdown_curve.png",
    "figures/style_or_industry_scores.png",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/base.yaml"))
    parser.add_argument("--data-path", type=Path, default=Path("data/input"))
    parser.add_argument("--outputs", type=Path, default=Path("outputs"))
    return parser.parse_args()


def metric_map(path: Path) -> dict[str, str]:
    frame = pd.read_csv(path, dtype=str)
    return dict(zip(frame["metric"], frame["value"]))


def assert_close(left: float, right: float, name: str, tolerance: float = 1e-10) -> None:
    if not np.isclose(left, right, rtol=tolerance, atol=tolerance):
        raise ValueError(f"{name} mismatch: {left} != {right}")


def main() -> int:
    args = parse_args()
    output = args.outputs.resolve()
    missing = sorted(path for path in REQUIRED_OUTPUTS if not (output / path).is_file())
    if missing:
        raise SystemExit("Missing outputs: " + ", ".join(missing))

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    prices = pd.read_csv(args.data_path / "prices.csv", parse_dates=["date"])
    nav = pd.read_csv(output / "nav_curve.csv", parse_dates=["date"])
    positions = pd.read_csv(output / "positions.csv", parse_dates=["date"])
    signals = pd.read_csv(
        output / "rotation_signals.csv", parse_dates=["signal_date", "execution_date"]
    )
    metrics = metric_map(output / "performance_metrics.csv")

    if prices.duplicated(["date", "asset"]).any():
        raise ValueError("Input prices contain duplicate date/asset rows")
    if prices[["date", "asset", "close"]].isna().any().any():
        raise ValueError("Input prices contain missing core observations")
    if not (signals["execution_date"] > signals["signal_date"]).all():
        raise ValueError("One or more executions are not after their signal date")
    selected = signals.loc[signals["selected"].astype(str).str.lower().eq("true")]
    selected_sums = selected.groupby("execution_date")["target_weight"].sum()
    if not np.allclose(selected_sums.to_numpy(), 1.0):
        raise ValueError("Selected target weights do not sum to one")
    position_sums = positions.groupby("date")["weight"].sum()
    if not np.allclose(position_sums.to_numpy(), 1.0):
        raise ValueError("Daily held-position weights do not sum to one")

    reconstructed_nav = (1 + nav["net_return"]).cumprod()
    if not np.allclose(reconstructed_nav, nav["strategy_nav"], rtol=1e-10, atol=1e-10):
        raise ValueError("Strategy NAV does not compound from net returns")
    reconstructed_benchmark = (1 + nav["benchmark_return"]).cumprod()
    if not np.allclose(
        reconstructed_benchmark, nav["benchmark_nav"], rtol=1e-10, atol=1e-10
    ):
        raise ValueError("Benchmark NAV does not compound from benchmark returns")
    if not np.allclose(
        nav["net_return"], nav["gross_return"] - nav["transaction_cost"]
    ):
        raise ValueError("Net return does not equal gross return less transaction cost")

    backtest = config["strategy"]["backtest"]
    cost_rate = (float(backtest["commission_bps"]) + float(backtest["slippage_bps"])) / 10_000
    if not np.allclose(nav["transaction_cost"], nav["turnover"] * cost_rate):
        raise ValueError("Transaction costs do not match turnover and configured bps")

    total_return = float(nav["strategy_nav"].iloc[-1] - 1)
    drawdown = nav["strategy_nav"] / nav["strategy_nav"].cummax() - 1
    assert_close(total_return, float(metrics["total_return"]), "total return")
    assert_close(float(drawdown.min()), float(metrics["maximum_drawdown"]), "maximum drawdown")
    assert_close(
        float(nav["transaction_cost"].sum()),
        float(metrics["total_transaction_cost"]),
        "total transaction cost",
    )
    if int(float(metrics["input_asset_count"])) != prices["asset"].nunique():
        raise ValueError("Reported asset count does not match inputs")

    summary = {
        "input_rows": len(prices),
        "assets": int(prices["asset"].nunique()),
        "industries": int(prices["industry"].nunique()) if "industry" in prices else 0,
        "input_start": prices["date"].min().date().isoformat(),
        "input_end": prices["date"].max().date().isoformat(),
        "first_valid_factor_date": metrics["first_valid_factor_date"],
        "backtest_start": nav["date"].min().date().isoformat(),
        "backtest_end": nav["date"].max().date().isoformat(),
        "signals": int(signals["signal_date"].nunique()),
        "rebalances": int((nav["turnover"] > 0).sum()),
        "total_return": total_return,
        "maximum_drawdown": float(drawdown.min()),
        "total_transaction_cost": float(nav["transaction_cost"].sum()),
    }
    print("VALID: " + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
