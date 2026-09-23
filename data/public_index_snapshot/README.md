# Fixed public-index snapshot

These six CSV files are the exact public snapshots used by the local and GitHub
Actions backtests. Their embedded source label is `Sina Finance via AkShare
stock_zh_index_daily`; coverage ends on 2026-07-31. They contain only public
index OHLCV observations and no account, credential, licensed stock panel or
private classification data.

`manifest.json` locks every source file by SHA-256, row count and date range and
also locks the deterministic `prices.csv` and `benchmark.csv` produced by:

```bash
python tools/prepare_open_index_data.py \
  --source-dir data/public_index_snapshot \
  --manifest data/public_index_snapshot/manifest.json \
  --output-dir data/input
```

The converter rejects any checksum, row-count, date-range, schema, symbol or
source-label mismatch before a backtest can run.
