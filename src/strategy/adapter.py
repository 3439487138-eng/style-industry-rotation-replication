"""Formal adapter connecting the complete strategy flow to run_replication.py."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

from replication.adapter import RunContext
from replication.config import ProjectConfig
from replication.errors import ConfigurationError

from .data import load_market_data
from .factors import FactorSettings, calculate_factor_scores
from .metrics import calculate_performance
from .portfolio import run_backtest
from .reporting import write_strategy_outputs
from .signals import generate_rotation_signals


def _format_metric(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def run_strategy(config: ProjectConfig, context: RunContext) -> dict[str, Any]:
    """Run data→factors→signals→portfolio→metrics→artifacts without fallbacks."""

    strategy = config.raw.get("strategy")
    if not isinstance(strategy, dict):
        raise ConfigurationError("strategy configuration must be a mapping")
    market = load_market_data(config)
    settings = FactorSettings.from_config(strategy)
    factors, factor_ic = calculate_factor_scores(market, settings)
    signals, targets = generate_rotation_signals(factors, strategy)
    backtest = run_backtest(factors, market.benchmark, targets, strategy)
    metrics, performance, monthly, drawdown = calculate_performance(
        backtest.daily, factor_ic, strategy
    )

    data_description = (
        f"Provider: local_files; prices: {market.prices_path.name} "
        f"({len(market.prices)} rows, {market.prices['asset'].nunique()} assets); "
        f"benchmark: {market.benchmark_path.name} ({len(market.benchmark)} rows); "
        f"coverage: {market.prices['date'].min().date()} to {market.prices['date'].max().date()}."
    )
    write_strategy_outputs(
        context.output_directory,
        backtest.daily,
        drawdown,
        performance,
        monthly,
        backtest.positions,
        signals,
        factor_ic,
        metrics,
        strategy,
        data_description,
    )

    metric_rows = [
        {"Metric": key, "Strategy": _format_metric(value)}
        for key, value in metrics.items()
    ]
    last_signal = signals.loc[signals["selected"]].tail(
        int(strategy.get("selection", {}).get("top_n", 3))
    )
    holdings_rows = [
        [
            pd.Timestamp(row.execution_date).date().isoformat(),
            row.asset,
            _format_metric(row.score),
            _format_metric(row.target_weight),
        ]
        for row in last_signal.itertuples()
    ]
    return {
        "paper": {
            "title": config.raw.get("project_name", "Style-industry rotation"),
            "citation": "Local research materials; practical adaptation",
            "source": config.raw.get("paper_source", "unavailable"),
        },
        "run": {
            "status": "adapted",
            "mode": config.raw.get("replication_mode", "practical adaptation"),
            "sample": f"{metrics['start_date']} to {metrics['end_date']}",
            "commit_sha": os.getenv("GITHUB_SHA", "unavailable in local execution"),
        },
        "summary": (
            "A complete current-run style/industry rotation backtest using momentum "
            "neutralized against Beta, size, volatility, liquidity and industry, "
            "with lagged periodic equal-weight execution and explicit costs."
        ),
        "metrics": metric_rows,
        "methodology": [
            {
                "Paper rule": "Control style and industry exposure",
                "Implementation": "Cross-sectional OLS residual against Beta, size, volatility, liquidity and industry dummies",
                "Status": "adapted",
            },
            {
                "Paper rule": "Generate alpha rather than passive exposure",
                "Implementation": "20-period momentum residual is used as the rotation score",
                "Status": "adapted",
            },
            {
                "Paper rule": "Portfolio construction and rebalancing",
                "Implementation": "Configured Top-N equal weight, next-close execution and explicit turnover costs",
                "Status": "unresolved",
            },
        ],
        "assumptions": [
            data_description,
            "Signal at date t uses only observations dated t or earlier.",
            "Trades execute at the next available close and affect subsequent returns.",
            "Missing held-asset returns stop the run rather than being imputed.",
            f"Commission plus slippage: {strategy['backtest']['commission_bps'] + strategy['backtest']['slippage_bps']} bps per unit one-way turnover.",
        ],
        "fidelity_gaps": [
            "Exact original score weights, Top-N, rebalance frequency and optimization constraints were unavailable; all are explicit configuration parameters.",
            "The strategy uses price/turnover/market-cap observations only; no fundamental disclosure-date data is used.",
        ],
        "figures": [
            {"title": "NAV curve", "path": "outputs/figures/nav_curve.png", "alt": "Strategy and benchmark NAV"},
            {"title": "Drawdown curve", "path": "outputs/figures/drawdown_curve.png", "alt": "Strategy drawdown"},
            {"title": "Style or industry scores", "path": "outputs/figures/style_or_industry_scores.png", "alt": "Neutralized rotation scores"},
        ],
        "tables": [
            {
                "title": "Latest selected assets",
                "columns": ["Execution date", "Asset", "Score", "Target weight"],
                "rows": holdings_rows,
            }
        ],
    }
