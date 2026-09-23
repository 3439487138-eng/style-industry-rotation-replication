"""Style exposures, robust cross-sectional transforms and neutralized score."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

from replication.errors import ConfigurationError, ReplicationUnavailable
from .data import MarketData


@dataclass(frozen=True)
class FactorSettings:
    momentum_window: int
    beta_window: int
    volatility_window: int
    liquidity_window: int
    winsorize_quantile: float
    neutralize_industry: bool
    min_cross_section: int
    mode: str = "stock_panel_neutralized"
    reversal_window: int = 20
    drawdown_window: int = 126
    momentum_weight: float = 0.25
    reversal_weight: float = 0.25
    volatility_weight: float = 0.25
    drawdown_weight: float = 0.25

    @classmethod
    def from_config(cls, strategy: Mapping[str, Any]) -> "FactorSettings":
        signal = strategy.get("signal", {})
        mode = str(strategy.get("mode", "stock_panel_neutralized")).lower()
        weights = signal.get("weights", {})
        settings = cls(
            momentum_window=int(signal.get("momentum_window", 20)),
            beta_window=int(signal.get("beta_window", 60)),
            volatility_window=int(signal.get("volatility_window", 20)),
            liquidity_window=int(signal.get("liquidity_window", 20)),
            winsorize_quantile=float(signal.get("winsorize_quantile", 0.01)),
            neutralize_industry=bool(signal.get("neutralize_industry", True)),
            min_cross_section=int(signal.get("min_cross_section", 5)),
            mode=mode,
            reversal_window=int(signal.get("reversal_window", 20)),
            drawdown_window=int(signal.get("drawdown_window", 126)),
            momentum_weight=float(weights.get("momentum", 0.25)),
            reversal_weight=float(weights.get("reversal", 0.25)),
            volatility_weight=float(weights.get("volatility", 0.25)),
            drawdown_weight=float(weights.get("drawdown", 0.25)),
        )
        if min(
            settings.momentum_window,
            settings.beta_window,
            settings.volatility_window,
            settings.liquidity_window,
        ) < 2:
            raise ConfigurationError("All rolling factor windows must be at least 2")
        if not 0 <= settings.winsorize_quantile < 0.5:
            raise ConfigurationError("winsorize_quantile must be in [0, 0.5)")
        if settings.min_cross_section < 3:
            raise ConfigurationError("min_cross_section must be at least 3")
        if settings.mode not in {"stock_panel_neutralized", "public_index_proxy"}:
            raise ConfigurationError(
                "strategy.mode must be stock_panel_neutralized or public_index_proxy"
            )
        if min(settings.reversal_window, settings.drawdown_window) < 2:
            raise ConfigurationError("reversal_window and drawdown_window must be at least 2")
        score_weights = (
            settings.momentum_weight,
            settings.reversal_weight,
            settings.volatility_weight,
            settings.drawdown_weight,
        )
        if min(score_weights) < 0 or sum(score_weights) <= 0:
            raise ConfigurationError("public index proxy weights must be non-negative and nonzero")
        return settings


def winsorize(series: pd.Series, quantile: float) -> pd.Series:
    lower = series.quantile(quantile)
    upper = series.quantile(1 - quantile)
    return series.clip(lower, upper)


def zscore(series: pd.Series) -> pd.Series:
    deviation = series.std(ddof=0)
    if deviation == 0 or not np.isfinite(deviation):
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / deviation


def _asset_exposures(group: pd.DataFrame, settings: FactorSettings) -> pd.DataFrame:
    ordered = group.sort_values("date").copy()
    ordered["asset_return"] = ordered["close"].pct_change(fill_method=None)
    ordered["momentum"] = ordered["close"].pct_change(
        settings.momentum_window, fill_method=None
    )
    ordered["volatility"] = ordered["asset_return"].rolling(
        settings.volatility_window, min_periods=settings.volatility_window
    ).std(ddof=0)
    ordered["liquidity"] = ordered["turnover"].rolling(
        settings.liquidity_window, min_periods=settings.liquidity_window
    ).mean()
    ordered["size"] = np.log(ordered["market_cap"])
    covariance = ordered["asset_return"].rolling(
        settings.beta_window, min_periods=settings.beta_window
    ).cov(ordered["benchmark_return"])
    variance = ordered["benchmark_return"].rolling(
        settings.beta_window, min_periods=settings.beta_window
    ).var(ddof=1)
    ordered["beta"] = covariance / variance.replace(0, np.nan)
    return ordered


def _neutralize_one_date(group: pd.DataFrame, settings: FactorSettings) -> pd.DataFrame:
    output = group.copy()
    required = ["momentum", "beta", "size", "volatility", "liquidity"]
    valid = output.dropna(subset=required).copy()
    if len(valid) < settings.min_cross_section:
        output["score"] = np.nan
        return output

    y = zscore(winsorize(valid["momentum"], settings.winsorize_quantile))
    style_columns = ["beta", "size", "volatility", "liquidity"]
    style = valid[style_columns].apply(
        lambda series: zscore(winsorize(series, settings.winsorize_quantile))
    )
    if settings.neutralize_industry:
        industry = pd.get_dummies(
            valid["industry"].astype(str), prefix="industry", drop_first=True, dtype=float
        )
        design = pd.concat([style, industry], axis=1)
    else:
        design = style
    design.insert(0, "constant", 1.0)
    matrix = design.to_numpy(dtype=float)
    target = y.to_numpy(dtype=float)
    coefficients, _, _, _ = np.linalg.lstsq(matrix, target, rcond=None)
    residual = target - matrix @ coefficients
    output["score"] = np.nan
    output.loc[valid.index, "score"] = residual
    return output


def _index_proxy_exposures(group: pd.DataFrame, settings: FactorSettings) -> pd.DataFrame:
    ordered = group.sort_values("date").copy()
    ordered["asset_return"] = ordered["close"].pct_change(fill_method=None)
    ordered["momentum"] = ordered["close"].pct_change(
        settings.momentum_window, fill_method=None
    )
    short_return = ordered["close"].pct_change(
        settings.reversal_window, fill_method=None
    )
    ordered["reversal"] = -short_return
    ordered["volatility"] = -ordered["asset_return"].rolling(
        settings.volatility_window, min_periods=settings.volatility_window
    ).std(ddof=0)
    rolling_peak = ordered["close"].rolling(
        settings.drawdown_window, min_periods=settings.drawdown_window
    ).max()
    ordered["drawdown"] = ordered["close"] / rolling_peak - 1
    return ordered


def _score_index_proxy_one_date(
    group: pd.DataFrame, settings: FactorSettings
) -> pd.DataFrame:
    output = group.copy()
    columns = ["momentum", "reversal", "volatility", "drawdown"]
    valid = output.dropna(subset=columns).copy()
    if len(valid) < settings.min_cross_section:
        output["score"] = np.nan
        return output
    standardized = valid[columns].apply(
        lambda series: zscore(winsorize(series, settings.winsorize_quantile))
    )
    weights = np.array(
        [
            settings.momentum_weight,
            settings.reversal_weight,
            settings.volatility_weight,
            settings.drawdown_weight,
        ],
        dtype=float,
    )
    weights /= weights.sum()
    output["score"] = np.nan
    output.loc[valid.index, "score"] = standardized.to_numpy() @ weights
    return output


def calculate_factor_scores(
    market: MarketData, settings: FactorSettings
) -> tuple[pd.DataFrame, pd.DataFrame]:
    benchmark = market.benchmark[["date", "close"]].copy()
    benchmark["benchmark_return"] = benchmark["close"].pct_change(fill_method=None)
    panel = market.prices.merge(
        benchmark[["date", "benchmark_return"]], on="date", how="left", validate="many_to_one"
    )
    if panel["benchmark_return"].isna().sum() > panel["asset"].nunique():
        raise ReplicationUnavailable("Benchmark returns are missing inside the price sample")

    exposure_function = (
        _index_proxy_exposures
        if settings.mode == "public_index_proxy"
        else _asset_exposures
    )
    score_function = (
        _score_index_proxy_one_date
        if settings.mode == "public_index_proxy"
        else _neutralize_one_date
    )
    calculated = [
        exposure_function(group, settings)
        for _, group in panel.groupby("asset", sort=True, observed=True)
    ]
    factors = pd.concat(calculated, ignore_index=True)
    scored = [
        score_function(group, settings)
        for _, group in factors.groupby("date", sort=True, observed=True)
    ]
    factors = pd.concat(scored, ignore_index=True).sort_values(["date", "asset"])
    if factors["score"].notna().sum() == 0:
        raise ReplicationUnavailable(
            "No valid factor scores were produced; check history length and min_cross_section"
        )

    factors["next_return"] = factors.groupby("asset", observed=True)["asset_return"].shift(-1)
    ic_rows: list[dict[str, object]] = []
    for date, group in factors.dropna(subset=["score", "next_return"]).groupby("date"):
        if len(group) < 3:
            continue
        rank_ic = group["score"].rank().corr(group["next_return"].rank())
        ic_rows.append({"date": date, "rank_ic": rank_ic, "asset_count": len(group)})
    factor_ic = pd.DataFrame(ic_rows)
    return factors.reset_index(drop=True), factor_ic
