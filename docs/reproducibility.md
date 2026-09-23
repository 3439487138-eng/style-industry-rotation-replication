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

`run_replication.py` is the supported entrypoint. It invokes `strategy.adapter:run_strategy`, which executes validated real-data loading, factor calculation, lagged rotation signals, portfolio construction, costs, returns, metrics and artifacts. The default `public_index_proxy` performs a current real-data run on six audited public index snapshots. The optional `stock_panel_neutralized` profile performs cross-sectional style/industry neutralization when its higher-fidelity fields are supplied.

## External requirements

The default public-index run requires no private account or credential. Six fixed public snapshots are committed under `data/public_index_snapshot/`; their manifest verifies every source file and the deterministic production inputs. The exact original proxy windows, score weights, Top-N, cost split and optimization constraints remain unavailable, so configured values are labelled practical adaptations. Saved charts or old outputs cannot satisfy a current execution. The higher-fidelity stock-panel profile still requires the authorized fields documented in `docs/data_requirements.md`.

The manual-only `Style-industry rotation full backtest` workflow rebuilds `data/input/`, removes all known generated outputs, runs the formal entrypoint and validators, uploads the outputs and log as an Artifact, and commits only current-run generated outputs. Push and pull-request checks remain read-only.

## Security

The previously embedded provider token was removed and must be rotated. Selected public research source is retained under its original AGPL-licensed paths after workstation paths were parameterized. Local databases, sensitive configuration, provider/server code outside the mapped research chain, generated artifacts, papers, and spreadsheets are excluded through `.gitignore` without deleting the local originals. The exact candidate set is recorded in `docs/upload-manifest.txt`.
