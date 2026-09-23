"""Formal adapter connecting the complete strategy flow to run_replication.py."""

from __future__ import annotations

import hashlib
import os
import subprocess
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


def _code_revision(project_root: object) -> str:
    github_sha = os.getenv("GITHUB_SHA")
    if github_sha:
        return github_sha
    root = str(project_root)
    safe_root = str(project_root).replace("\\", "/")
    command = ["git", "-c", f"safe.directory={safe_root}", "-C", root]
    try:
        revision = subprocess.run(
            command + ["rev-parse", "--short=12", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        dirty = subprocess.run(
            command + ["status", "--porcelain"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        return revision + ("-dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "unavailable in local execution"


def _sha256(path: object) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_strategy(config: ProjectConfig, context: RunContext) -> dict[str, Any]:
    """Run data→factors→signals→portfolio→metrics→artifacts without fallbacks."""

    strategy = config.raw.get("strategy")
    if not isinstance(strategy, dict):
        raise ConfigurationError("strategy configuration must be a mapping")
    market = load_market_data(config)
    settings = FactorSettings.from_config(strategy)
    if market.profile == "public_index_proxy" and settings.mode != "public_index_proxy":
        raise ConfigurationError(
            "data.profile public_index_proxy requires strategy.mode public_index_proxy"
        )
    if market.profile == "stock_panel" and settings.mode != "stock_panel_neutralized":
        raise ConfigurationError(
            "data.profile stock_panel requires strategy.mode stock_panel_neutralized"
        )
    factors, factor_ic = calculate_factor_scores(market, settings)
    signals, targets = generate_rotation_signals(factors, strategy)
    backtest = run_backtest(factors, market.benchmark, targets, strategy)
    metrics, performance, monthly, drawdown = calculate_performance(
        backtest.daily, factor_ic, strategy
    )
    first_factor_date = factors.loc[factors["score"].notna(), "date"].min()
    metrics.update(
        {
            "input_profile": market.profile,
            "input_asset_count": int(market.prices["asset"].nunique()),
            "input_industry_count": (
                int(market.prices["industry"].nunique())
                if "industry" in market.prices
                else 0
            ),
            "first_valid_factor_date": first_factor_date.date().isoformat(),
        }
    )
    performance = pd.DataFrame(
        [{"metric": key, "value": value} for key, value in metrics.items()]
    )

    source_description = ""
    if "source" in market.prices:
        sources = sorted(market.prices["source"].astype(str).unique())
        source_description = f" sources: {'; '.join(sources)};"
    data_description = (
        f"Provider: local_files; profile: {market.profile}; prices: {market.prices_path.name} "
        f"({len(market.prices)} rows, {market.prices['asset'].nunique()} assets); "
        f"benchmark: {market.benchmark_path.name} ({len(market.benchmark)} rows); "
        f"{source_description} "
        f"coverage: {market.prices['date'].min().date()} to {market.prices['date'].max().date()}; "
        f"prices_sha256: {_sha256(market.prices_path)}; "
        f"benchmark_sha256: {_sha256(market.benchmark_path)}."
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
    if settings.mode == "public_index_proxy":
        summary = (
            "A complete current-run public-index style rotation backtest using "
            "momentum, reversal, low-volatility and drawdown proxy scores, with "
            "lagged monthly Top-1 execution and explicit costs."
        )
        methodology = [
            {
                "Paper rule": "Publicly reproducible Barra-style proxy",
                "Implementation": "Cross-sectional composite of momentum, reversal, low volatility and drawdown across six Chinese equity indices",
                "Status": "adapted",
            },
            {
                "Paper rule": "Periodic style rotation",
                "Implementation": "Configured Top-1 equal weight, next-close execution and explicit turnover costs",
                "Status": "adapted",
            },
            {
                "Paper rule": "Individual-stock style and industry neutralization",
                "Implementation": "Unavailable because no real stock-level market-cap/turnover/industry panel was found; no fields were fabricated",
                "Status": "unavailable",
            },
        ]
        fidelity_gaps = [
            "This medium-fidelity public-index proxy cannot replace the unavailable individual-stock industry-neutralized baseline.",
            "Exact production lookbacks and score weights were not present in the recovered engine; configured windows and equal component weights are explicit practical adaptations.",
            "Volume is retained as source provenance but is not relabelled as turnover or used as a liquidity factor.",
        ]
    else:
        summary = (
            "A complete current-run stock-panel style/industry rotation backtest "
            "using momentum neutralized against Beta, size, volatility, liquidity "
            "and industry, with lagged periodic execution and explicit costs."
        )
        methodology = [
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
        ]
        fidelity_gaps = [
            "Exact original score weights, Top-N, rebalance frequency and optimization constraints were unavailable; all are explicit configuration parameters.",
            "The strategy uses price/turnover/market-cap observations only; no fundamental disclosure-date data is used.",
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
            "commit_sha": _code_revision(context.project_root),
        },
        "summary": summary,
        "metrics": metric_rows,
        "methodology": methodology,
        "assumptions": [
            data_description,
            "Signal at date t uses only observations dated t or earlier.",
            "Trades execute at the next available close and affect subsequent returns.",
            "Missing held-asset returns stop the run rather than being imputed.",
            f"Commission plus slippage: {strategy['backtest']['commission_bps'] + strategy['backtest']['slippage_bps']} bps per unit one-way turnover.",
        ],
        "fidelity_gaps": fidelity_gaps,
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
