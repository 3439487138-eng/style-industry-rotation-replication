"""Performance statistics computed only from current-run portfolio returns."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from replication.errors import ReplicationUnavailable


def calculate_performance(
    daily: pd.DataFrame,
    factor_ic: pd.DataFrame,
    strategy: Mapping[str, Any],
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if daily.empty:
        raise ReplicationUnavailable("Backtest returned no daily observations")
    backtest = strategy.get("backtest", {})
    annualization = int(backtest.get("annualization_days", 252))
    risk_free_rate = float(backtest.get("risk_free_rate", 0.025))
    observations = max(len(daily) - 1, 1)
    years = observations / annualization

    total_return = float(daily["strategy_nav"].iloc[-1] - 1)
    annual_return = float((1 + total_return) ** (1 / years) - 1) if years > 0 else np.nan
    annual_volatility = float(daily["net_return"].std(ddof=1) * np.sqrt(annualization))
    sharpe = (
        float((annual_return - risk_free_rate) / annual_volatility)
        if annual_volatility > 0
        else np.nan
    )
    drawdown = daily["strategy_nav"] / daily["strategy_nav"].cummax() - 1
    max_drawdown = float(drawdown.min())
    indexed = daily.set_index("date")
    monthly = (1 + indexed["net_return"]).resample("ME").prod() - 1
    monthly_returns = monthly.rename("return").reset_index()
    monthly_win_rate = float((monthly > 0).mean()) if len(monthly) else np.nan
    rebalance_count = int((daily["turnover"] > 0).sum())
    annual_turnover = float(daily["turnover"].sum() / years) if years > 0 else np.nan
    benchmark_total = float(daily["benchmark_nav"].iloc[-1] - 1)
    mean_rank_ic = (
        float(factor_ic["rank_ic"].mean())
        if not factor_ic.empty and factor_ic["rank_ic"].notna().any()
        else np.nan
    )

    metrics: dict[str, object] = {
        "start_date": daily["date"].iloc[0].date().isoformat(),
        "end_date": daily["date"].iloc[-1].date().isoformat(),
        "trading_days": int(observations),
        "total_return": total_return,
        "annualized_return": annual_return,
        "annualized_volatility": annual_volatility,
        "sharpe_ratio": sharpe,
        "maximum_drawdown": max_drawdown,
        "monthly_win_rate": monthly_win_rate,
        "rebalance_count": rebalance_count,
        "annualized_turnover": annual_turnover,
        "total_transaction_cost": float(daily["transaction_cost"].sum()),
        "benchmark_total_return": benchmark_total,
        "mean_rank_ic": mean_rank_ic,
    }
    numeric_values = [
        value
        for key, value in metrics.items()
        if key not in {"start_date", "end_date"} and isinstance(value, float)
    ]
    if any(not np.isfinite(value) for value in numeric_values):
        raise ReplicationUnavailable("One or more required performance metrics are non-finite")
    performance_table = pd.DataFrame(
        [{"metric": key, "value": value} for key, value in metrics.items()]
    )
    drawdown_table = pd.DataFrame({"date": daily["date"], "drawdown": drawdown})
    return metrics, performance_table, monthly_returns, drawdown_table
