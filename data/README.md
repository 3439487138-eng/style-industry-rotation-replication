# Input data contract

Place only authorized `prices.csv` and `benchmark.csv` under `data/input/`, or override the location with `REPLICATION_DATA_PATH` / `--data-path`. Input and private download directories are ignored by Git.

The complete schema, timing rules and missing-data policy are documented in `docs/data_requirements.md`. Header-only templates live in `data/templates/`. The production loader rejects missing, duplicate, non-finite and invalid observations and never substitutes demo or synthetic data.
