"""Execute close-to-close holdings with explicit lag, turnover and costs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

from replication.errors import ConfigurationError, ReplicationUnavailable


@dataclass(frozen=True)
class BacktestResult:
    daily: pd.DataFrame
    positions: pd.DataFrame


def _one_way_turnover(old: dict[str, float], new: dict[str, float]) -> float:
    assets = set(old) | set(new)
    asset_change = sum(abs(new.get(asset, 0.0) - old.get(asset, 0.0)) for asset in assets)
    old_cash = 1.0 - sum(old.values())
    new_cash = 1.0 - sum(new.values())
    return 0.5 * (asset_change + abs(new_cash - old_cash))


def run_backtest(
    factors: pd.DataFrame,
    benchmark: pd.DataFrame,
    targets: dict[pd.Timestamp, dict[str, float]],
    strategy: Mapping[str, Any],
) -> BacktestResult:
    backtest = strategy.get("backtest", {})
    commission_bps = float(backtest.get("commission_bps", 5.0))
    slippage_bps = float(backtest.get("slippage_bps", 5.0))
    missing_policy = str(backtest.get("missing_held_return", "fail")).lower()
    if min(commission_bps, slippage_bps) < 0:
        raise ConfigurationError("commission_bps and slippage_bps must be non-negative")
    if missing_policy != "fail":
        raise ConfigurationError("Only missing_held_return='fail' is supported")
    total_cost_rate = (commission_bps + slippage_bps) / 10_000.0

    returns = factors.pivot(index="date", columns="asset", values="asset_return").sort_index()
    benchmark_returns = benchmark.set_index("date")["close"].sort_index().pct_change(fill_method=None)
    first_execution = min(targets)
    all_dates = returns.index
    first_location = all_dates.get_loc(first_execution)
    start_location = max(0, int(first_location) - 1)
    dates = all_dates[start_location:]
    if len(dates) < 2:
        raise ReplicationUnavailable("Not enough dates after the first rebalance")

    current: dict[str, float] = {}
    strategy_nav = 1.0
    benchmark_nav = 1.0
    daily_rows: list[dict[str, object]] = []
    position_rows: list[dict[str, object]] = []

    for index, date in enumerate(dates):
        if index == 0:
            gross_return = 0.0
            benchmark_return = 0.0
        else:
            held_returns = returns.loc[date].reindex(list(current))
            if current and held_returns.isna().any():
                missing_assets = held_returns[held_returns.isna()].index.tolist()
                raise ReplicationUnavailable(
                    f"Held assets have missing returns on {date.date()}: {', '.join(missing_assets)}"
                )
            gross_return = sum(
                current[asset] * float(held_returns.loc[asset]) for asset in current
            )
            benchmark_value = benchmark_returns.reindex([date]).iloc[0]
            if pd.isna(benchmark_value):
                raise ReplicationUnavailable(f"Benchmark return missing on {date.date()}")
            benchmark_return = float(benchmark_value)

        turnover = 0.0
        transaction_cost = 0.0
        if date in targets:
            turnover = _one_way_turnover(current, targets[date])
            transaction_cost = turnover * total_cost_rate
            current = targets[date].copy()
        net_return = gross_return - transaction_cost
        if not np.isfinite(net_return) or net_return <= -1:
            raise ReplicationUnavailable(f"Invalid portfolio return on {date.date()}")
        strategy_nav *= 1 + net_return
        benchmark_nav *= 1 + benchmark_return
        daily_rows.append(
            {
                "date": date,
                "gross_return": gross_return,
                "transaction_cost": transaction_cost,
                "net_return": net_return,
                "turnover": turnover,
                "strategy_nav": strategy_nav,
                "benchmark_return": benchmark_return,
                "benchmark_nav": benchmark_nav,
            }
        )
        for asset, weight in sorted(current.items()):
            position_rows.append({"date": date, "asset": asset, "weight": weight})

    return BacktestResult(pd.DataFrame(daily_rows), pd.DataFrame(position_rows))
