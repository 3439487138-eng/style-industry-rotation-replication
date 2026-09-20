"""Legacy four-stock Alpha example; not the formal replication entrypoint.

The regression formula is preserved from the original script. The referenced
MongoDB collections are not populated by this repository's supported runner,
so this command is incomplete research material and must not be presented as a
successful strategy reproduction.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CALCULATOR_PATH = (
    ROOT
    / "panda_factor"
    / "panda_factor"
    / "panda_factor"
    / "analysis"
    / "alpha_calculator.py"
)


def _load_calculator_class():
    specification = importlib.util.spec_from_file_location(
        "legacy_alpha_calculator", CALCULATOR_PATH
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"Cannot load legacy calculator: {CALCULATOR_PATH}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.AlphaCalculator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=os.getenv("PANDA_FACTOR_MONGO_URI"))
    parser.add_argument(
        "--db-name", default=os.getenv("PANDA_FACTOR_MONGO_DB", "panda_factor")
    )
    parser.add_argument("--start-date", default="20240101")
    parser.add_argument("--end-date", default="20241231")
    parser.add_argument(
        "--stocks",
        nargs="+",
        default=["000001.SZ", "000002.SZ", "600000.SH", "600036.SH"],
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.mongo_uri:
        print("UNAVAILABLE: set PANDA_FACTOR_MONGO_URI or pass --mongo-uri")
        return 3
    calculator_class = _load_calculator_class()
    calculator = calculator_class(mongo_uri=args.mongo_uri, db_name=args.db_name)
    result = calculator.calculate_alpha(
        stock_list=args.stocks,
        start_date=args.start_date,
        end_date=args.end_date,
        weights=None,
    )
    print("=" * 50)
    print("阿尔法计算结果（旧研究模块）")
    print("=" * 50)
    print(f"阿尔法 (α):      {result['alpha']:.6f}")
    print(f"阿尔法 T 统计量：  {result['alpha_tstat']:.4f}")
    print(f"阿尔法 P 值：     {result['alpha_pvalue']:.4f}")
    print(f"市场贝塔 (β_m):  {result['beta_market']:.4f}")
    print(f"R 平方：         {result['r_squared']:.4f}")
    print("=" * 50)
    print(result["regression_summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
