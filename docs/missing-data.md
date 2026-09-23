# Current Missing Data

The audited repository does not contain a sufficiently long, complete real panel for the formal strategy.

Missing production inputs:

- `data/input/prices.csv` with `date, asset, close, turnover, market_cap, industry, asset_type`;
- `data/input/benchmark.csv` with `date, close`;
- point-in-time industry history if the investable assets are stocks;
- provenance, extraction timestamp, adjustment convention, coverage and redistribution permission for both files.

The local `计算机.xlsx` contains only two endpoint dates for a small set of indices. It cannot support rolling factors, periodic rebalancing, transaction costs, or reliable performance statistics and is therefore not used.

Until the files above are supplied, `python run_replication.py --config config/base.yaml` exits nonzero and lists the missing files. No output metrics are generated.
