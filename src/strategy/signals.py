"""Generate lag-safe periodic rotation targets from neutralized scores."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from replication.errors import ConfigurationError, ReplicationUnavailable


FREQUENCIES = {"weekly": "W-FRI", "monthly": "M", "quarterly": "Q"}


def generate_rotation_signals(
    factors: pd.DataFrame, strategy: Mapping[str, Any]
) -> tuple[pd.DataFrame, dict[pd.Timestamp, dict[str, float]]]:
    selection = strategy.get("selection", {})
    backtest = strategy.get("backtest", {})
    top_n = int(selection.get("top_n", 3))
    weighting = str(selection.get("weighting", "equal")).lower()
    frequency_name = str(backtest.get("rebalance_frequency", "monthly")).lower()
    if top_n < 1:
        raise ConfigurationError("selection.top_n must be positive")
    if weighting != "equal":
        raise ConfigurationError("Only evidence-backed equal weighting is currently supported")
    if frequency_name not in FREQUENCIES:
        raise ConfigurationError("rebalance_frequency must be weekly, monthly, or quarterly")

    valid = factors.dropna(subset=["score"]).copy()
    valid["period"] = valid["date"].dt.to_period(FREQUENCIES[frequency_name])
    signal_dates = valid.groupby("period", observed=True)["date"].max().sort_values()
    trading_dates = pd.Index(sorted(factors["date"].drop_duplicates()))
    rows: list[dict[str, object]] = []
    targets: dict[pd.Timestamp, dict[str, float]] = {}

    for signal_date in signal_dates:
        future_dates = trading_dates[trading_dates > signal_date]
        if future_dates.empty:
            continue
        execution_date = pd.Timestamp(future_dates[0])
        cross_section = valid.loc[valid["date"].eq(signal_date)].sort_values(
            ["score", "asset"], ascending=[False, True]
        )
        selected = cross_section.head(top_n)
        if len(selected) < top_n:
            continue
        weight = 1.0 / len(selected)
        target = dict(zip(selected["asset"], [weight] * len(selected)))
        targets[execution_date] = target
        selected_assets = set(selected["asset"])
        ranks = cross_section["score"].rank(method="first", ascending=False).astype(int)
        for (_, item), rank in zip(cross_section.iterrows(), ranks):
            rows.append(
                {
                    "signal_date": signal_date,
                    "execution_date": execution_date,
                    "asset": item["asset"],
                    "asset_type": item["asset_type"],
                    "industry": item["industry"],
                    "score": item["score"],
                    "rank": int(rank),
                    "selected": item["asset"] in selected_assets,
                    "target_weight": weight if item["asset"] in selected_assets else 0.0,
                }
            )
    if not targets:
        raise ReplicationUnavailable(
            "No rebalance targets were generated; sample may be shorter than factor windows"
        )
    return pd.DataFrame(rows), targets
