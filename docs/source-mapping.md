# Source Mapping

This mapping separates preserved research source from the supported replication entrypoint. “Complete” means complete for the stated narrow function, not a complete paper backtest.

| Original file | GitHub file | Main function | Complete? | In `run_replication.py`? | Reason / limitation |
|---|---|---|---|---|---|
| `panda_factor/scripts/style_industry_neutralize_demo.py` | `examples/style_industry_neutralize_demo.py` | 20-day momentum; rolling Beta, size, volatility and liquidity; SW industry/style OLS residual; Top-50 next-day toy PnL | Partial/demo | No | Moved under examples; fallback benchmark proxy and no production portfolio/cost/report chain |
| `panda_factor/panda_factor/panda_factor/analysis/alpha_calculator.py` | same path | Portfolio excess-return regression on market, style and industry factors | Partial | No | Requires undocumented MongoDB collections; fixed 3% annual risk-free simplification |
| `scripts/calculate_alpha.py` | same path | Parameterized CLI for the legacy Alpha calculator | Example only | No | Four-stock defaults are retained as an example, not a strategy universe |
| `panda_factor/panda_factor/panda_factor/analysis/factor_func.py` | same path | Adjusted prices/future returns, tradability cleaning, MAD/3σ processing, size/industry/Barra neutralization, z-score and quantile grouping | Function collection | No | Depends on local `panda_data`; grouping adds tiny random noise for tied bins; legacy file roots are now environment-driven |
| `panda_factor/panda_factor/panda_factor/analysis/factor.py` | same path | Group holdings, turnover, IC/Rank-IC, group PnL, annualized return/volatility, drawdown, Sharpe, tracking error and win rates | Factor-analysis engine | No | Generic single-factor engine, not the paper’s exact portfolio strategy; private runtime dependencies remain |
| `panda_factor/panda_factor/panda_factor/analysis/factor_analysis.py` | same path | Single-factor analysis orchestration | Partial | No | Requires `panda_data`, MongoDB handlers and task state |
| `panda_factor/panda_factor/panda_factor/analysis/factor_analysis_workflow.py` | same path | Workflow variant with adjusted returns, grouping and task logging | Partial | No | Former workstation CSV path is now required via `--input`; private runtime still required |
| `panda_factor/panda_factor/panda_factor/analysis/factor_ic_workflow.py` | same path | IC-oriented factor workflow | Partial | No | Generic factor test, not style/industry rotation construction |
| `panda_factor/panda_factor/panda_factor/generate/*.py` | same paths | Factor base class, formula loader, wrappers, error handling and common factor transformations | Utility layer | No | Public research utilities; no paper-specific signal combination or portfolio optimizer |
| `panda_factor/panda_factor/panda_factor/data/*.py` | same paths | Abstract/Panda data provider and market-data cleaner | Interface layer | No | Concrete `panda_data` database runtime and authorized observations are not included |
| `panda_factor/panda_common/panda_common/{config.py,logger_config.py,handlers,models,utils}` (selected files) | same paths | Environment-aware config loader, database abstraction, logging, chart/parameter models and stock-code utility | Supporting subset | No | Sensitive `config.yaml` is excluded; only support files required to understand the research chain are retained |
| `大类.py` | same path | Public AkShare interval comparison for eight style indices | Complete for interval comparison | No | Not a backtest, signal engine or portfolio strategy |
| Existing neutralization, factor and performance fragments | `src/strategy/*.py` | Real-data loader, style exposures, OLS neutralized score, periodic signals, equal-weight execution, costs, NAV, metrics and artifacts | Complete practical adaptation | Yes | Unknown production choices are explicit config parameters; no synthetic production data |
| `run_replication.py` | same path | Validate production inputs, load `strategy.adapter:run_strategy`, execute the full chain and generate auditable reports | Complete orchestration | Yes | Missing authorized data fails nonzero and lists required files |

## Safety-only changes

- `factor_func.py`: replaced contributor workstation roots with `PANDA_FACTOR_DATA_ROOT` and `PANDA_FACTOR_LIBRARY_ROOT`; formulas are unchanged.
- `factor_analysis_workflow.py`: replaced a contributor CSV path with required `--input`.
- `alpha_calculator.py` and `scripts/calculate_alpha.py`: removed default Mongo endpoint and require `PANDA_FACTOR_MONGO_URI` or `--mongo-uri`.
- `panda_common/config.py`: logs configuration key names instead of the complete configuration values.
- `style_industry_neutralize_demo.py`: moved under `examples/` and strengthened the existing demo/toy warning; calculations are unchanged.

## Intentionally excluded source and artifacts

The rest of the local `panda_factor` monorepo is not needed to preserve the identified strategy research chain. Server/API code, provider-specific ingestion services, duplicated build copies, local MongoDB data, caches, logs, `.Temp`, nested `.git`, config values and generated intermediates remain ignored. A historical embedded Mongo connection string found in an unselected minute-reader comment was removed during the security audit even though that file remains excluded.

The supported adapter is a clean implementation of the rules that can be confirmed from the preserved fragments. It imports no toy PnL and labels unknown production choices as configurable practical adaptations.
