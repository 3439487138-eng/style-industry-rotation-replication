from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from replication.config import ProjectConfig
from replication.adapter import RunContext
from replication.errors import ReplicationUnavailable
from replication.report import validate_payload
from strategy.adapter import run_strategy
from strategy.data import MarketData, load_market_data, normalize_asset_code
from strategy.factors import FactorSettings, calculate_factor_scores
from strategy.metrics import calculate_performance
from strategy.portfolio import run_backtest
from strategy.signals import generate_rotation_signals


def _market_data(tmp_path: Path, future_multiplier: float = 1.0) -> MarketData:
    dates = pd.bdate_range("2024-01-02", periods=12)
    rows: list[dict[str, object]] = []
    for asset_number in range(8):
        base = 90 + asset_number * 3
        for day_number, date in enumerate(dates):
            close = base * (1 + 0.002 * (asset_number - 3) * day_number + 0.0002 * day_number**2)
            if day_number > 8:
                close *= future_multiplier if asset_number == 0 else 1.0
            rows.append(
                {
                    "date": date,
                    "asset": f"A{asset_number}",
                    "close": close,
                    "turnover": 0.01 + asset_number * 0.001 + day_number * 0.0001,
                    "market_cap": 1_000_000 + asset_number * 100_000 + day_number * 1_000,
                    "industry": f"I{asset_number % 2}",
                    "asset_type": "style" if asset_number < 4 else "industry",
                }
            )
    benchmark = pd.DataFrame(
        {"date": dates, "close": 100 * (1 + pd.Series(range(len(dates))) * 0.001)}
    )
    return MarketData(pd.DataFrame(rows), benchmark, tmp_path / "prices.csv", tmp_path / "benchmark.csv")


def _settings() -> FactorSettings:
    return FactorSettings(
        momentum_window=3,
        beta_window=3,
        volatility_window=3,
        liquidity_window=3,
        winsorize_quantile=0.01,
        neutralize_industry=True,
        min_cross_section=8,
    )


def test_asset_code_normalization() -> None:
    assert normalize_asset_code("000001.XSHE") == "000001.SZ"
    assert normalize_asset_code("600000.XSHG") == "600000.SH"


def test_factor_scores_do_not_use_future_prices(tmp_path: Path) -> None:
    baseline, _ = calculate_factor_scores(_market_data(tmp_path), _settings())
    changed, _ = calculate_factor_scores(_market_data(tmp_path, future_multiplier=5.0), _settings())
    cutoff = pd.Timestamp("2024-01-12")
    left = baseline.loc[baseline["date"].le(cutoff), ["date", "asset", "score"]]
    right = changed.loc[changed["date"].le(cutoff), ["date", "asset", "score"]]
    pd.testing.assert_frame_equal(left.reset_index(drop=True), right.reset_index(drop=True))


def test_signal_executes_after_signal_date(tmp_path: Path) -> None:
    factors, _ = calculate_factor_scores(_market_data(tmp_path), _settings())
    strategy = {
        "selection": {"top_n": 3, "weighting": "equal"},
        "backtest": {"rebalance_frequency": "weekly"},
    }
    signals, targets = generate_rotation_signals(factors, strategy)
    assert not signals.empty
    assert (signals["execution_date"] > signals["signal_date"]).all()
    assert all(abs(sum(weights.values()) - 1) < 1e-12 for weights in targets.values())


def test_transaction_cost_and_next_period_return_are_applied() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    factors = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "asset": ["A"] * 3 + ["B"] * 3,
            "asset_return": [np.nan, 0.01, 0.02, np.nan, -0.01, 0.0],
        }
    )
    benchmark = pd.DataFrame({"date": dates, "close": [100.0, 101.0, 102.0]})
    result = run_backtest(
        factors,
        benchmark,
        {dates[1]: {"A": 1.0}},
        {"backtest": {"commission_bps": 10, "slippage_bps": 0, "missing_held_return": "fail"}},
    )
    assert result.daily.loc[1, "turnover"] == pytest.approx(1.0)
    assert result.daily.loc[1, "transaction_cost"] == pytest.approx(0.001)
    assert result.daily.loc[2, "gross_return"] == pytest.approx(0.02)


def test_missing_held_return_fails_instead_of_being_filled() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    factors = pd.DataFrame(
        {
            "date": dates,
            "asset": ["A", "A", "A"],
            "asset_return": [np.nan, 0.01, np.nan],
        }
    )
    benchmark = pd.DataFrame({"date": dates, "close": [100.0, 101.0, 102.0]})
    with pytest.raises(ReplicationUnavailable, match="Held assets have missing returns"):
        run_backtest(
            factors,
            benchmark,
            {dates[1]: {"A": 1.0}},
            {
                "backtest": {
                    "commission_bps": 0,
                    "slippage_bps": 0,
                    "missing_held_return": "fail",
                }
            },
        )


def test_performance_uses_compounded_nav_and_peak_to_trough_drawdown() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    daily = pd.DataFrame(
        {
            "date": dates,
            "net_return": [0.0, 0.10, -0.20],
            "strategy_nav": [1.0, 1.10, 0.88],
            "benchmark_nav": [1.0, 1.02, 1.01],
            "turnover": [0.0, 1.0, 0.0],
            "transaction_cost": [0.0, 0.001, 0.0],
        }
    )
    factor_ic = pd.DataFrame({"rank_ic": [0.2]})
    metrics, _, monthly, drawdown = calculate_performance(
        daily,
        factor_ic,
        {"backtest": {"annualization_days": 252, "risk_free_rate": 0.0}},
    )
    assert metrics["total_return"] == pytest.approx(-0.12)
    assert metrics["maximum_drawdown"] == pytest.approx(-0.20)
    assert monthly.loc[0, "return"] == pytest.approx(-0.12)
    assert drawdown.loc[2, "drawdown"] == pytest.approx(-0.20)


def test_data_loader_reports_missing_columns(tmp_path: Path) -> None:
    data_path = tmp_path / "input"
    data_path.mkdir()
    pd.DataFrame({"date": ["2024-01-01"], "asset": ["A"]}).to_csv(
        data_path / "prices.csv", index=False
    )
    pd.DataFrame({"date": ["2024-01-01"], "close": [100]}).to_csv(
        data_path / "benchmark.csv", index=False
    )
    config = ProjectConfig(
        raw={
            "sample_start": "2024-01-01",
            "sample_end": "2024-12-31",
            "data": {"prices_file": "prices.csv", "benchmark_file": "benchmark.csv"},
        },
        project_root=tmp_path,
        config_path=tmp_path / "config.yaml",
        adapter="strategy.adapter:run_strategy",
        data_provider="local_files",
        data_path=data_path,
        display_data_path="input",
        output_directory=tmp_path / "outputs",
        payload_path=tmp_path / "outputs/report.json",
        report_path=tmp_path / "outputs/report.html",
        required_env=(),
    )
    with pytest.raises(ReplicationUnavailable, match="missing columns"):
        load_market_data(config)


def test_complete_adapter_writes_all_outputs_only_to_temp_fixture(tmp_path: Path) -> None:
    market = _market_data(tmp_path)
    data_path = tmp_path / "input"
    data_path.mkdir()
    market.prices.to_csv(data_path / "prices.csv", index=False)
    market.benchmark.to_csv(data_path / "benchmark.csv", index=False)
    output = tmp_path / "outputs"
    raw = {
        "project_name": "fixture",
        "replication_mode": "practical adaptation",
        "paper_source": "fixture-only",
        "sample_start": "2024-01-01",
        "sample_end": "2024-12-31",
        "data": {"prices_file": "prices.csv", "benchmark_file": "benchmark.csv"},
        "strategy": {
            "signal": {
                "momentum_window": 3,
                "beta_window": 3,
                "volatility_window": 3,
                "liquidity_window": 3,
                "winsorize_quantile": 0.01,
                "neutralize_industry": True,
                "min_cross_section": 8,
            },
            "selection": {"top_n": 3, "weighting": "equal"},
            "backtest": {
                "rebalance_frequency": "weekly",
                "commission_bps": 5.0,
                "slippage_bps": 5.0,
                "annualization_days": 252,
                "risk_free_rate": 0.025,
                "missing_held_return": "fail",
            },
        },
    }
    config = ProjectConfig(
        raw=raw,
        project_root=tmp_path,
        config_path=tmp_path / "config.yaml",
        adapter="strategy.adapter:run_strategy",
        data_provider="local_files",
        data_path=data_path,
        display_data_path="input",
        output_directory=output,
        payload_path=output / "report.json",
        report_path=output / "report.html",
        required_env=(),
    )
    context = RunContext(tmp_path, config.config_path, data_path, output)
    payload = run_strategy(config, context)
    validate_payload(payload)
    expected = {
        "performance_metrics.csv",
        "monthly_returns.csv",
        "nav_curve.csv",
        "positions.csv",
        "rotation_signals.csv",
        "factor_effectiveness.csv",
        "backtest_report.md",
        "figures/nav_curve.png",
        "figures/drawdown_curve.png",
        "figures/style_or_industry_scores.png",
    }
    assert all((output / relative).is_file() for relative in expected)
