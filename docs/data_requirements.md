# Data Requirements

The formal strategy reads real observations from a local directory. No fixture, demo, cached result, or generated market value is accepted by the production entrypoint.

## `prices.csv`

One row per trading date and investable asset:

| Field | Type | Meaning |
|---|---|---|
| `date` | date | Observation date; parseable by pandas |
| `asset` | string | Stock, style index, industry index, or fund code |
| `close` | positive float | Adjusted close appropriate for return calculation |
| `turnover` | non-negative float | Consistently scaled turnover/liquidity observation |
| `market_cap` | positive float | Consistently scaled market capitalization |
| `industry` | string | Point-in-time industry label used in neutralization |
| `asset_type` | string | `style`, `industry`, `stock`, or another documented class |

Rows must be unique by `date,asset`. Every selected asset needs uninterrupted closes during its holding period; a missing held return stops the run. The loader never forward-fills, interpolates, or substitutes zero.

Industry labels must be point-in-time when stocks can change industry. A static current classification introduces look-ahead and classification bias and must be disclosed by the data provider.

## `benchmark.csv`

| Field | Type | Meaning |
|---|---|---|
| `date` | date | Trading date |
| `close` | positive float | Adjusted benchmark close |

It must cover the full price date range. Beta uses rolling covariance of asset and benchmark returns divided by rolling benchmark variance.

## Timing and reliability

- Momentum, Beta, volatility, liquidity, size and the neutralized score at date `t` use only rows dated `t` or earlier.
- Cross-sectional winsorization, z-score and industry regression use assets observed at the same date.
- Signals are formed at a period's last available close.
- Rebalancing occurs at the next available close; new weights affect returns only after that close.
- Commission and slippage are charged from one-way turnover on the rebalance date.
- No accounting fields are currently used. If fundamental factors are added, values must be joined by actual publication date, never report period alone.
- Delisted or suspended assets require an explicit real return/valuation observation. Missing held observations fail closed.

Header-only templates are in `data/templates/`. Put authorized files in ignored `data/input/`, or pass `--data-path` / `REPLICATION_DATA_PATH`.
