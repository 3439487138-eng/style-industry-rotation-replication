# 贝塔配置：风格行业轮动体系化方案

这是一个可执行的风格/行业轮动回测工程。正式入口已经连接完整的“数据→因子→评分→轮动信号→组合→调仓成本→净值→指标→报告”链路，不再使用 `UNAVAILABLE` 策略占位器，也不会把 demo、测试夹具、缓存或旧结果作为正式回测证据。

当前默认配置已经使用老师项目中可追溯的 6 个 AkShare/Sina 公开指数快照完成真实数据回测。公开仓库提交固定快照、逐文件 SHA-256 清单和转换脚本；本地与 GitHub Actions 均由它们确定性生成被 Git 忽略的 `data/input/`。由于仍无完整个股市值、换手率及点时行业面板，本次结果是老师项目同样采用的中等保真“公开指数代理”，不是个股行业中性化收益复现。

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
2. 标准化指数代码并保留原始数据源标签。
3. 默认公开指数模式按资产计算收益、126 日动量、20 日反转、20 日低波动及 126 日回撤代理。
4. 在同一交易日截面上去极值、标准化，并按配置权重合成评分。
5. 可选个股面板模式仍支持 Beta、规模、波动率、流动性和行业虚拟变量 OLS 中性化，但需要另行提供真实字段。
6. 在每个月最后一个可用收盘生成排名和 Top-1 等权目标。
7. 下一交易日收盘调仓，新权重只影响之后的收盘到收盘收益，避免把信号当日收益计入。
8. 按含现金的一向换手率扣除手续费和滑点。
9. 缺少持仓资产收益时立即失败，不填零、不前向填充。
10. 计算净值、基准、月度收益、回撤、Sharpe、胜率、调仓次数、换手率和 Rank IC。
11. 输出 CSV、PNG、Markdown、JSON 和独立 HTML 报告。

正式实现位于 `src/strategy/`；`examples/style_industry_neutralize_demo.py` 仅保留原始研究依据，不进入正式调用链。

## 数据要求

默认公开指数代理使用被 Git 忽略的：

- `prices.csv`：`date,asset,asset_name,close,volume,asset_type,source`
- `benchmark.csv`：`date,close,source`

公开快照位于 `data/public_index_snapshot/`。转换命令为 `python tools/prepare_open_index_data.py --source-dir data/public_index_snapshot --manifest data/public_index_snapshot/manifest.json --output-dir data/input`；转换前会核验来源文件的校验值、行数、日期、字段和代码，转换后还会核验 `prices.csv` 与 `benchmark.csv` 的校验值。字段定义、时间对齐及个股面板要求见 [data_requirements.md](docs/data_requirements.md)。模板位于 `data/templates/`，不包含虚构观察值；更高保真度仍缺的字段见 [missing-data.md](docs/missing-data.md)。

`计算机.xlsx` 只有少量指数的两个端点，无法计算滚动因子、月度调仓和可靠绩效，正式策略不会使用它。

## 配置参数

主要参数位于 `config/base.yaml`：

- `momentum_window`：指数代理动量窗口，默认 126；
- `reversal_window`：短期反转窗口，默认 20；
- `drawdown_window`：回撤代理窗口，默认 126；
- `volatility_window`：波动率窗口，默认 20；
- `weights`：动量、反转、低波动和回撤代理权重，当前均为 0.25；
- `winsorize_quantile`：截面缩尾比例；
- `neutralize_industry`：是否加入行业虚拟变量；
- `min_cross_section`：单日最少有效资产数；
- `top_n`：入选资产数，默认 1；
- `rebalance_frequency`：`weekly`、`monthly` 或 `quarterly`；
- `commission_bps`、`slippage_bps`：单边交易成本；
- `risk_free_rate`：Sharpe 使用的年化无风险利率。

精确生产窗口、代理权重和成本拆分无法从已恢复引擎中确认，因此均可配置并在报告中标为适配项；没有通过拟合老师保存的历史收益来选择参数。

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

- `Style-industry rotation public checks`：在 `push` 和 `pull_request` 上安装锁定依赖、校验配置、编译源码、运行测试并审计上传清单。测试夹具不会写入正式 `outputs/`，也不代表收益结果。
- `Style-industry rotation full backtest`：通过 `workflow_dispatch` 手动触发。工作流核验仓库内固定公开快照的 SHA-256，自动生成 `data/input/prices.csv` 和 `benchmark.csv`，清除上次生成物后执行 `python run_replication.py --config config/base.yaml`，运行回测与报告校验，检查绩效和净值文件，上传 `outputs/` 与日志为 Artifact，并把本次重新计算的公开结果提交到所选分支。任何步骤失败都会使运行失败，不使用 `continue-on-error`。

完整公开指数回测不需要 GitHub Secrets、Token 或授权数据库。固定快照的来源、覆盖期和校验值见 [data/public_index_snapshot/README.md](data/public_index_snapshot/README.md) 与 `manifest.json`。

## 原始研究源码

`panda_factor/` 中可公开的 AGPL 研究源码被选择性保留，包括因子分析、因子生成、中性化、持仓、换手率、收益和指标计算。完整映射见 [source-mapping.md](docs/source-mapping.md)，上传候选见 [upload-manifest.txt](docs/upload-manifest.txt)。

这些旧模块用于依据追溯；正式策略调用链只使用 `src/strategy/`。历史 demo 已移至 `examples/` 并明确标注，不能作为正式回测结果。

## 当前结果与限制

- 实际数据：6 个中国权益指数，源标签为 `Sina Finance via AkShare stock_zh_index_daily`，原始覆盖 2018-01-02 至 2026-07-31。
- 实际回测区间：2018-07-31 至 2026-07-31；累计收益 -1.9703%，年化收益 -0.2582%，年化波动 21.3101%，Sharpe -0.1294，最大回撤 -57.1591%。
- 月度胜率 50.5155%，调仓 49 次，年化单向换手 6.3649，总计入日收益的交易成本率 4.90%。同期沪深300基准累计收益 30.4333%。
- 结果来自当前命令重新计算的真实公开指数数据，不是老师历史结果或测试夹具；较差收益也未被替换或调参美化。
- 公开指数代理不能替代个股行业中性化。个股模式仍缺少真实市值、换手率和点时行业分类。
- 原材料没有提供完整生产规则，配置化默认值均属于 practical adaptation，不能据此声称精确复现论文收益。
- 研究输出不构成投资建议。
