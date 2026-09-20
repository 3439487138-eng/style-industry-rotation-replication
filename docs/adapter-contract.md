# Strategy Adapter Contract

The engineering layer deliberately does not implement the strategy. A production adapter is a thin callable around the authorized original engine.

## Callable

Configure `strategy.adapter` as `module:function`. The function receives:

```python
def run(config: ProjectConfig, context: RunContext) -> dict:
    ...
```

It must read real inputs from `context.data_path`, execute the original calculation in its original order, and return only outputs computed during that invocation. It must not silently substitute mock, demo, random, interpolated, cached, or old results.

## Required payload

The returned mapping must include `paper`, `run`, `summary`, `metrics`, `methodology`, `assumptions`, `fidelity_gaps`, `figures`, and `tables`. `run.status` must be `matched`, `adapted`, or `extended`. Each methodology row uses one of `matched`, `adapted`, `extended`, `unavailable`, or `unresolved` in its `Status` field.

For a portfolio backtest, metrics should include total and annualized return, annualized volatility, Sharpe convention, maximum drawdown and duration, benchmark/excess return, turnover, and costs when available. Unavailable values must be labelled `unavailable`, not written as zero.

Figures use repository-relative paths and are embedded into the standalone report. The adapter should include data provider/source identifiers, extraction time, row counts, coverage, missing observations, transformations, sample dates, parameters, execution time, and code revision in the payload.

Adapter exceptions propagate as a stable nonzero `ADAPTER_ERROR`. Invalid payloads and report write failures propagate as `REPORT_ERROR`; no older report is used as fallback.
