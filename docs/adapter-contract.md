# Strategy Adapter Contract

The repository now includes an executable strategy implementation at
`src/strategy/`. The configured production adapter is
`strategy.adapter:run_strategy`; it connects the engineering runner to the
real-data factor, signal, portfolio and reporting pipeline.

Two real-data profiles are implemented. The default medium-fidelity public-index
profile follows the teacher project's documented momentum, reversal, volatility
and drawdown proxy method. The optional stock-panel profile preserves 20-day
momentum, beta/size/volatility/liquidity exposures, cross-sectional winsorization
and standardization, industry-dummy OLS neutralization, residual ranking, and
next-period return evaluation. Rules that cannot be recovered from source (for
example exact proxy windows/weights, production Top-N and trading costs) remain
explicit configuration parameters and are reported as practical adaptations.

## Callable

Configure `strategy.adapter` as `module:function`. The function receives:

```python
def run(config: ProjectConfig, context: RunContext) -> dict:
    ...
```

It must read real inputs from `context.data_path`, validate their fields and
coverage, execute the configured calculation in order, and return only outputs
computed during that invocation. It must not silently substitute mock, demo,
random, interpolated, cached, or old results. Missing authorized data is an
expected `UNAVAILABLE` condition with a nonzero exit code; no performance output
is generated in that case.

## Required payload

The returned mapping must include `paper`, `run`, `summary`, `metrics`, `methodology`, `assumptions`, `fidelity_gaps`, `figures`, and `tables`. `run.status` must be `matched`, `adapted`, or `extended`. Each methodology row uses one of `matched`, `adapted`, `extended`, `unavailable`, or `unresolved` in its `Status` field.

For a portfolio backtest, metrics should include total and annualized return, annualized volatility, Sharpe convention, maximum drawdown and duration, benchmark/excess return, turnover, and costs when available. Unavailable values must be labelled `unavailable`, not written as zero.

Figures use repository-relative paths and are embedded into the standalone report. The adapter should include data provider/source identifiers, extraction time, row counts, coverage, missing observations, transformations, sample dates, parameters, execution time, and code revision in the payload.

Adapter exceptions propagate as a stable nonzero `ADAPTER_ERROR`. Invalid payloads and report write failures propagate as `REPORT_ERROR`; no older report is used as fallback.
