# 贝塔配置：风格行业轮动体系化方案

这是对现有研究材料的工程化整理，不是重新编写的策略。仓库提供可审计配置、薄适配器接口、稳定失败语义、测试、独立 HTML 报告契约和手动 GitHub Actions。它不会用随机数据、示例回测、缓存或历史图表冒充本次复现结果。

## 当前结论

现有材料不足以形成完整、可运行的真实策略链。能够确认的源码片段包括：

- Tushare/本地 MongoDB 的行情、指数、申万行业和基础因子采集代码；
- 动量、Beta、规模、波动率、流动性及行业/风格中性化的示例计算；
- 固定四只股票的 Alpha 计算脚本；
- 八个公开风格指数的两端点区间收益比较（`大类.py`）。

缺失的是把这些片段连接为论文策略所需的精确定义：完整因子集与合成权重、风格/行业信号规则、股票池过滤、组合优化约束、调仓时点与成交规则、交易成本、完整绩效评价及生产报告。现有 `panda_factor` 示例明确是 toy backtest，`大类.py` 只是区间比较，因此二者都没有接入正式入口。

默认执行会清晰返回 `UNAVAILABLE`（退出码 3）。只有获得授权的原始策略引擎后，才应通过薄适配器连接；不得在调度层重写算法。

## 受支持的调用链

```text
config/base.yaml + .env/CLI overrides
             │
             ▼
run_replication.py
  ├─ 校验配置、真实数据位置及所需环境变量
  ├─ 动态加载 strategy.adapter（module:function）
  ├─ 一次性调用原始策略适配器
  ├─ 校验本次运行返回的证据 payload
  └─ 原子写入 outputs/report.json 与独立 outputs/report.html
```

配置优先级为命令行 > 环境变量 > YAML。数据路径可用 `--data-path` 或 `REPLICATION_DATA_PATH` 覆盖，适配器可用 `--adapter` 或 `REPLICATION_STRATEGY_ADAPTER` 覆盖。

## 目录

- `config/base.yaml`：可提交、无密钥的基础配置。
- `src/replication/`：配置、适配器与报告工程层，不包含策略算法。
- `tools/`：配置、payload 和 HTML 校验/渲染工具。
- `tests/`：配置、失败路径、路径兼容、适配器和报告契约测试。
- `data/README.md`：授权输入数据约定；`data/input/` 不提交。
- `outputs/README.md`：本次真实运行输出约定。
- `大类.py`：补充性公开指数观察，不是回测入口。

`panda_factor/` 不再整体排除。拟上传仓库会选择性保留其 AGPL 许可证、因子分析、因子生成、数据接口、中性化示例和必要公共工具源码；MongoDB 数据、服务端代码、构建产物、敏感配置及私有数据源实现仍被忽略。逐文件关系见 [`docs/source-mapping.md`](docs/source-mapping.md)，候选清单见 [`docs/upload-manifest.txt`](docs/upload-manifest.txt)。

这些旧模块属于“不完整研究源码”：它们保留了 Beta、动量、规模、波动率、流动性、行业/风格中性化、分组持仓、换手率、收益和指标计算，但仍依赖未提交的 `panda_data` 运行环境与 MongoDB 集合。`run_replication.py` 不会自动调用它们。

## Windows 本地验证

项目现有虚拟环境使用 Python 3.12。所有验证均从项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools\validate_config.py --structure-only
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe run_replication.py --help
.\.venv\Scripts\python.exe run_replication.py --check
```

最后一条在默认配置下应返回退出码 3，因为真实适配器和授权数据尚未提供。这是预期结果，不代表测试失败。

## 接入原始引擎

适配器必须是 `module:function`，接受 `(ProjectConfig, RunContext)` 并返回当前运行生成的报告 payload。完整接口与字段见 [`docs/adapter-contract.md`](docs/adapter-contract.md)。例如：

```powershell
$env:REPLICATION_DATA_PATH = '.\authorized-data'
$env:REPLICATION_STRATEGY_ADAPTER = 'my_private_adapter:run'
.\.venv\Scripts\python.exe run_replication.py --check
.\.venv\Scripts\python.exe run_replication.py
```

凭证名称写入 `data.required_env`，值只放在本地 `.env` 或 GitHub Secrets。选定真实适配器后，还需在工作流 `env` 中逐项映射同名 Secret；当前没有选定数据源，因此工作流不会暴露任何 Secret。不得将 Token、密码、Cookie 或私有数据写入 YAML 或提交到仓库。

旧研究文件读取路径通过 `PANDA_FACTOR_DATA_ROOT` 和 `PANDA_FACTOR_LIBRARY_ROOT` 参数化；旧 Alpha 示例通过 `PANDA_FACTOR_MONGO_URI` 和 `PANDA_FACTOR_MONGO_DB` 配置。它们不属于正式入口，连接信息也不会写入仓库。

## GitHub Actions

工作流仅支持 `workflow_dispatch`。默认只安装依赖、检查配置结构并运行测试；勾选 `run_replication` 后才会使用同一个 `run_replication.py` 执行真实策略、校验报告、上传 artifact，并只提交 `outputs/report.json` 和 `outputs/report.html`。在接入合法数据源前不要勾选该选项，也不配置定时运行。

## 安全与限制

曾嵌入源码的 Tushare Token 已移除，应在服务商侧撤销并轮换。当前没有生成 `outputs/report.json` 或 `outputs/report.html`，也没有声称复现收益。研究输出不构成投资建议。
