# Backtest Report

This report was generated from the current run's declared real CSV inputs. It is a practical adaptation, not a claim that the paper's unavailable production rules were exactly matched.

## Data

Provider: local_files; profile: public_index_proxy; prices: prices.csv (11999 rows, 6 assets); benchmark: benchmark.csv (2081 rows);  sources: Sina Finance via AkShare stock_zh_index_daily; coverage: 2018-01-02 to 2026-07-31; prices_sha256: 6d6634d48e8193de4fc3887f1c04021f568b4522ed69243a33477c577e8c6f2b; benchmark_sha256: 5f0325175635d29fdb45622dbdde1caec6b4ce230b2689a3c206a57f3c22a0fc.

The current run is the medium-fidelity public-index proxy. It uses no market-cap, turnover or industry field because no real local panel for those fields was found; volume is not treated as turnover.

## Performance

- start_date: 2018-07-31
- end_date: 2026-07-31
- trading_days: 1940
- total_return: -0.019703
- annualized_return: -0.002582
- annualized_volatility: 0.213101
- sharpe_ratio: -0.129430
- maximum_drawdown: -0.571591
- monthly_win_rate: 0.505155
- rebalance_count: 49
- annualized_turnover: 6.364948
- total_transaction_cost: 0.049000
- benchmark_total_return: 0.304333
- mean_rank_ic: -0.003275
- input_profile: public_index_proxy
- input_asset_count: 6
- input_industry_count: 0
- first_valid_factor_date: 2018-07-11

## Execution assumptions

- Signals use observations available through each signal close.
- Rebalancing occurs at the next available close; new weights affect subsequent close-to-close returns.
- Equal weighting and selection breadth follow the explicit configuration.
- Commission and slippage are deducted from portfolio return on each rebalance.
- Missing returns for held assets stop the run; they are never filled with zero.
- No fundamental fields are used, so financial statement publication-date alignment is not applicable.

## Configuration

```text
{'adapter': 'strategy.adapter:run_strategy', 'mode': 'public_index_proxy', 'signal': {'raw_factor': 'style_proxy_composite', 'momentum_window': 126, 'reversal_window': 20, 'drawdown_window': 126, 'beta_window': 60, 'volatility_window': 20, 'liquidity_window': 20, 'winsorize_quantile': 0.01, 'neutralize_industry': False, 'min_cross_section': 4, 'weights': {'momentum': 0.25, 'reversal': 0.25, 'volatility': 0.25, 'drawdown': 0.25}}, 'selection': {'top_n': 1, 'weighting': 'equal'}, 'backtest': {'rebalance_frequency': 'monthly', 'commission_bps': 5.0, 'slippage_bps': 5.0, 'annualization_days': 252, 'risk_free_rate': 0.025, 'missing_held_return': 'fail'}}
```

Research output only; not investment advice.
