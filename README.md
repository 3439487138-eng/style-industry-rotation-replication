# 贝塔配置：风格行业轮动体系化方案

这是一个可执行的风格/行业轮动回测工程。正式入口已经连接完整的“数据→因子→中性化评分→轮动信号→组合→调仓成本→净值→指标→报告”链路，不再使用 `UNAVAILABLE` 策略占位器，也不会把 demo、测试夹具、缓存或旧结果作为正式回测证据。

当前仓库没有可公开且足够完整的真实输入面板，因此尚未生成或声称任何真实收益结果。提供符合字段契约的授权数据后，正式入口会执行完整回测；数据缺失时会非零退出并列出缺失文件。

## 策略依据与边界

仓库材料能够确认：

- 原始因子采用 20 日动量；
- 风格暴露包含 Beta、规模、波动率和流动性；
- 对原始因子做截面去极值、标准化，并对风格暴露和行业虚拟变量进行 OLS 中性化；
- 中性化残差作为纯 Alpha/强弱评分；
- 已有 demo 使用 Top-N 等权和下一期收益。

材料没有给出生产策略的精确 Top-N、调仓频率、成本拆分及优化约束。因此 [base.yaml](config/base.yaml) 将它们设为显式参数，默认值属于 `practical adaptation`，不是对论文规则的虚构声明。

## 完整策略流程

1. 读取并验证真实 `prices.csv` 和 `benchmark.csv`。
2. 标准化股票、指数或基金代码。
3. 按资产计算收益、动量、滚动 Beta、波动率、流动性和对数规模。
4. 在同一交易日截面上对动量及风格暴露去极值、标准化。
5. 用 Beta、规模、波动率、流动性及行业虚拟变量解释动量，OLS 残差作为轮动评分。
6. 在每个配置周期最后一个可用收盘生成排名和 Top-N 等权目标。
7. 下一交易日收盘调仓，新权重只影响之后的收盘到收盘收益，避免把信号当日收益计入。
8. 按含现金的一向换手率扣除手续费和滑点。
9. 缺少持仓资产收益时立即失败，不填零、不前向填充。
10. 计算净值、基准、月度收益、回撤、Sharpe、胜率、调仓次数、换手率和 Rank IC。
11. 输出 CSV、PNG、Markdown、JSON 和独立 HTML 报告。

正式实现位于 `src/strategy/`；`examples/style_industry_neutralize_demo.py` 仅保留原始研究依据，不进入正式调用链。

## 数据要求

将授权数据放入被 Git 忽略的 `data/input/`：

- `prices.csv`：`date,asset,close,turnover,market_cap,industry,asset_type`
- `benchmark.csv`：`date,close`

字段定义、时间对齐、停牌/退市和行业点时要求见 [data_requirements.md](docs/data_requirements.md)。只有表头的模板位于 `data/templates/`，不包含虚构观察值。当前缺失清单见 [missing-data.md](docs/missing-data.md)。

`计算机.xlsx` 只有少量指数的两个端点，无法计算滚动因子、月度调仓和可靠绩效，正式策略不会使用它。

## 配置参数

主要参数位于 `config/base.yaml`：

- `momentum_window`：原始动量窗口，默认 20；
- `beta_window`：Beta 窗口，默认 60；
- `volatility_window`：波动率窗口，默认 20；
- `liquidity_window`：流动性窗口，默认 20；
- `winsorize_quantile`：截面缩尾比例；
- `neutralize_industry`：是否加入行业虚拟变量；
- `min_cross_section`：单日最少有效资产数；
- `top_n`：入选资产数，默认 3；
- `rebalance_frequency`：`weekly`、`monthly` 或 `quarterly`；
- `commission_bps`、`slippage_bps`：单边交易成本；
- `risk_free_rate`：Sharpe 使用的年化无风险利率。

默认 Top-3、月频和成本拆分无法从原材料精确确认，因此均可配置并在报告中标为适配项。

## 本地运行

Windows：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools\validate_config.py --structure-only
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe run_replication.py --config config/base.yaml
```

使用外部授权目录：

```powershell
.\.venv\Scripts\python.exe run_replication.py `
  --config config/base.yaml `
  --data-path .\authorized\rotation-data
```

成功运行会生成：

- `outputs/performance_metrics.csv`
- `outputs/monthly_returns.csv`
- `outputs/nav_curve.csv`
- `outputs/positions.csv`
- `outputs/rotation_signals.csv`
- `outputs/factor_effectiveness.csv`
- `outputs/backtest_report.md`
- `outputs/report.json`、`outputs/report.html`
- `outputs/figures/nav_curve.png`
- `outputs/figures/drawdown_curve.png`
- `outputs/figures/style_or_industry_scores.png`

## GitHub Actions

工作流分为两层：

- `push`、`pull_request`、普通 `workflow_dispatch`：安装依赖、校验配置、编译源码、运行 16+ 项测试，并在隔离临时目录中验证完整策略链。测试夹具不会写入正式 `outputs/`，也不代表收益结果。
- 手动勾选 `run_full`：从 `REPLICATION_DATA_ARCHIVE_URL` 下载授权 ZIP，可选使用 `REPLICATION_DATA_ARCHIVE_TOKEN`，随后执行正式入口、报告校验、Artifact 上传和同分支结果提交。任一步失败都会使工作流失败。

私有 ZIP 根目录应直接包含 `prices.csv` 和 `benchmark.csv`。以上变量在 GitHub 中配置为 Secrets，数据目录、下载文件和日志不会被强制加入 Git。

## 原始研究源码

`panda_factor/` 中可公开的 AGPL 研究源码被选择性保留，包括因子分析、因子生成、中性化、持仓、换手率、收益和指标计算。完整映射见 [source-mapping.md](docs/source-mapping.md)，上传候选见 [upload-manifest.txt](docs/upload-manifest.txt)。

这些旧模块用于依据追溯；正式策略调用链只使用 `src/strategy/`。历史 demo 已移至 `examples/` 并明确标注，不能作为正式回测结果。

## 当前结果与限制

- 实际完成的真实数据回测：尚未完成，原因是缺少完整授权输入面板。
- 当前正式命令结果：非零退出并报告缺少 `prices.csv`、`benchmark.csv`。
- 测试结果只证明公式、时序、成本、失败路径和报告生成可执行，不代表论文收益复现。
- 原材料没有提供完整生产规则，配置化默认值均属于 practical adaptation。
- 研究输出不构成投资建议。
