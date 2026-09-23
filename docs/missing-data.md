# Remaining Higher-Fidelity Data Gap

The current public-index proxy backtest is complete and uses six real equity-index
snapshots. The following inputs remain unavailable only for the higher-fidelity
individual-stock industry-neutralized baseline:

- a stock-level panel with `date, asset, close, turnover, market_cap, industry, asset_type`;
- point-in-time industry history if the investable assets are stocks;
- adjustment conventions and redistribution permission for that stock panel.

The local `计算机.xlsx` contains only two endpoint dates for a small set of indices. It cannot support rolling factors, periodic rebalancing, transaction costs, or reliable performance statistics and is therefore not used.

The default configuration does not fabricate these fields. It selects the
medium-fidelity `public_index_proxy`, whose successful outputs are stored under
`outputs/`. Switching to `stock_panel_neutralized` still requires the missing
authorized fields above.
