"""Write auditable CSV, Markdown and chart artifacts for a successful run."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from replication.errors import ReportError


def _save_figure(figure: plt.Figure, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(path, dpi=150, bbox_inches="tight")
    except OSError as exc:
        raise ReportError(f"Cannot write figure '{path}': {exc}") from exc
    finally:
        plt.close(figure)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False, encoding="utf-8-sig")
    except OSError as exc:
        raise ReportError(f"Cannot write output '{path}': {exc}") from exc


def write_strategy_outputs(
    output: Path,
    daily: pd.DataFrame,
    drawdown: pd.DataFrame,
    performance: pd.DataFrame,
    monthly_returns: pd.DataFrame,
    positions: pd.DataFrame,
    signals: pd.DataFrame,
    factor_ic: pd.DataFrame,
    metrics: Mapping[str, object],
    strategy_config: Mapping[str, Any],
    data_description: str,
) -> None:
    figures = output / "figures"
    _write_csv(performance, output / "performance_metrics.csv")
    _write_csv(monthly_returns, output / "monthly_returns.csv")
    _write_csv(
        daily[
            [
                "date",
                "gross_return",
                "transaction_cost",
                "net_return",
                "turnover",
                "strategy_nav",
                "benchmark_return",
                "benchmark_nav",
            ]
        ],
        output / "nav_curve.csv",
    )
    _write_csv(positions, output / "positions.csv")
    _write_csv(signals, output / "rotation_signals.csv")
    _write_csv(factor_ic, output / "factor_effectiveness.csv")

    figure, axis = plt.subplots(figsize=(10, 5))
    axis.plot(daily["date"], daily["strategy_nav"], label="Strategy")
    axis.plot(daily["date"], daily["benchmark_nav"], label="Benchmark")
    axis.set_title("Net asset value")
    axis.set_ylabel("NAV")
    axis.grid(alpha=0.25)
    axis.legend()
    _save_figure(figure, figures / "nav_curve.png")

    figure, axis = plt.subplots(figsize=(10, 4))
    axis.fill_between(drawdown["date"], drawdown["drawdown"], 0, color="#b54242", alpha=0.7)
    axis.set_title("Strategy drawdown")
    axis.set_ylabel("Drawdown")
    axis.grid(alpha=0.25)
    _save_figure(figure, figures / "drawdown_curve.png")

    score_view = signals.pivot(index="signal_date", columns="asset", values="score").tail(12)
    figure, axis = plt.subplots(figsize=(max(8, score_view.shape[1] * 0.6), 5))
    image = axis.imshow(score_view.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn")
    axis.set_xticks(range(len(score_view.columns)), score_view.columns, rotation=60, ha="right")
    axis.set_yticks(
        range(len(score_view.index)),
        [pd.Timestamp(value).date().isoformat() for value in score_view.index],
    )
    axis.set_title("Style / industry neutralized scores")
    figure.colorbar(image, ax=axis, label="Score")
    _save_figure(figure, figures / "style_or_industry_scores.png")

    metric_lines = "\n".join(
        f"- {key}: {value:.6f}" if isinstance(value, float) else f"- {key}: {value}"
        for key, value in metrics.items()
    )
    mode = str(strategy_config.get("mode", "stock_panel_neutralized"))
    method_note = (
        "The current run is the medium-fidelity public-index proxy. It uses no "
        "market-cap, turnover or industry field because no real local panel for "
        "those fields was found; volume is not treated as turnover."
        if mode == "public_index_proxy"
        else "The current run uses the configured stock-panel industry-neutralized model."
    )
    report = f"""# Backtest Report

This report was generated from the current run's declared real CSV inputs. It is a practical adaptation, not a claim that the paper's unavailable production rules were exactly matched.

## Data

{data_description}

{method_note}

## Performance

{metric_lines}

## Execution assumptions

- Signals use observations available through each signal close.
- Rebalancing occurs at the next available close; new weights affect subsequent close-to-close returns.
- Equal weighting and selection breadth follow the explicit configuration.
- Commission and slippage are deducted from portfolio return on each rebalance.
- Missing returns for held assets stop the run; they are never filled with zero.
- No fundamental fields are used, so financial statement publication-date alignment is not applicable.

## Configuration

```text
{strategy_config}
```

Research output only; not investment advice.
"""
    try:
        (output / "backtest_report.md").write_text(report, encoding="utf-8")
    except OSError as exc:
        raise ReportError(f"Cannot write backtest_report.md: {exc}") from exc
