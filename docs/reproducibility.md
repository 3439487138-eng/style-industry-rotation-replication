# Reproducibility Notes

## Audited baseline

- Primary source: local `贝塔配置：风格行业轮动体系化方案.pdf` (excluded from GitHub pending redistribution permission)
- Replication mode: practical adaptation
- Intended sample: 2018-01-01 to 2026-07-31
- Configured benchmark: `000300.SH`
- Configured turnover cost: 10 basis points per unit turnover
- Paper Replicator skill snapshot SHA-256: `A086CE12A88874C66B1CE006169B343F2151552001B8B1E3BFB5E446CEA6260F`

## Source audit

The local `panda_factor/` tree contains provider collectors, MongoDB storage, generic factor code, and a style/industry neutralization demo. The demo labels itself a toy backtest, uses a fallback market proxy, and does not implement the paper's complete signal, portfolio, execution, cost, evaluation, and report chain. `scripts/calculate_alpha.py` is a disconnected four-stock Alpha calculation. `大类.py` compares endpoint returns for eight public style indices and is not a backtest.

The paper describes the principles of risk-model neutralization and style/industry exposure constraints, but the available material does not provide enough exact definitions and parameters to reconstruct the production algorithm without invention.

## Execution boundary

`run_replication.py` is the supported entrypoint. It invokes `strategy.adapter:run_strategy`, which executes validated real-data loading, factor calculation, cross-sectional neutralization, lagged rotation signals, portfolio construction, costs, returns, metrics and artifacts. Missing production data remains `unavailable`; the strategy implementation itself is no longer a placeholder.

## External requirements

An authorized run must supply the CSV fields documented in `docs/data_requirements.md` and their provenance. The exact original Top-N, rebalance frequency, cost split and optimization constraints remain unavailable, so configured values are labelled practical adaptations. Saved charts or old outputs cannot satisfy a current execution.

## Security

The previously embedded provider token was removed and must be rotated. Selected public research source is retained under its original AGPL-licensed paths after workstation paths were parameterized. Local databases, sensitive configuration, provider/server code outside the mapped research chain, generated artifacts, papers, and spreadsheets are excluded through `.gitignore` without deleting the local originals. The exact candidate set is recorded in `docs/upload-manifest.txt`.
