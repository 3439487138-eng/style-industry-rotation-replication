# Input data contract

Generated `prices.csv` and `benchmark.csv` belong under `data/input/`, or at the location selected by `REPLICATION_DATA_PATH` / `--data-path`. Generated inputs and private data directories are ignored by Git.

The exact six AkShare/Sina public-index source snapshots used by the default run are versioned under `data/public_index_snapshot/`. Their hashes, row counts and coverage are locked by `manifest.json`; `tools/prepare_open_index_data.py` deterministically creates and verifies the ignored production inputs. These files contain public index OHLCV only—no account, credential, licensed stock panel or private classification data.

The complete schemas for `public_index_proxy` and `stock_panel` are documented in `docs/data_requirements.md`. Header-only templates live in `data/templates/`. The production loader rejects missing, duplicate, non-finite and invalid observations and never substitutes demo or synthetic data.
