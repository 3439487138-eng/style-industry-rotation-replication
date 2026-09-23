# Input data contract

Place only authorized `prices.csv` and `benchmark.csv` under `data/input/`, or override the location with `REPLICATION_DATA_PATH` / `--data-path`. Input and private download directories are ignored by Git. The current local files were reproducibly converted from the teacher project's six AkShare/Sina public-index snapshots; they are not committed.

The complete schemas for `public_index_proxy` and `stock_panel` are documented in `docs/data_requirements.md`. Header-only templates live in `data/templates/`. The production loader rejects missing, duplicate, non-finite and invalid observations and never substitutes demo or synthetic data.
