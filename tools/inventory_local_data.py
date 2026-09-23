"""Inventory local market-data candidates without changing source files."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd


SUPPORTED = {".csv", ".xls", ".xlsx", ".parquet", ".feather", ".db", ".sqlite", ".sqlite3"}
SKIPPED_DIRECTORIES = {".git", ".venv", "venv", "__pycache__", "build", "dist", "node_modules"}
FIELD_ALIASES = {
    "date": {"date", "trade_date", "datetime", "time", "日期", "交易日期", "时间"},
    "asset": {"asset", "symbol", "code", "ts_code", "证券代码", "股票代码", "代码"},
    "close": {"close", "adj_close", "adjusted_close", "收盘", "收盘价", "复权收盘价"},
    "volume": {"volume", "vol", "成交量"},
    "turnover": {"turnover", "turnover_rate", "amount", "成交额", "换手率"},
    "market_cap": {"market_cap", "total_mv", "circ_mv", "总市值", "流通市值", "市值"},
    "industry": {"industry", "industry_name", "sw_industry", "申万行业", "行业", "行业分类"},
    "asset_type": {"asset_type", "type", "资产类型", "证券类型"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Directory to scan recursively")
    parser.add_argument("--output", type=Path, help="Optional CSV inventory path")
    return parser.parse_args()


def candidate_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part.lower() in SKIPPED_DIRECTORIES for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in SUPPORTED | {".pkl", ".pickle"}:
            files.append(path)
    return sorted(files, key=lambda item: str(item).casefold())


def mapped_fields(columns: Iterable[object]) -> list[str]:
    normalized = {str(column).strip().lower() for column in columns}
    return [
        field
        for field, aliases in FIELD_ALIASES.items()
        if normalized.intersection({alias.lower() for alias in aliases})
    ]


def date_summary(frame: pd.DataFrame) -> tuple[str, str, str]:
    normalized = {str(column).strip().lower(): column for column in frame.columns}
    for alias in FIELD_ALIASES["date"]:
        column = normalized.get(alias.lower())
        if column is None:
            continue
        parsed = pd.to_datetime(frame[column], errors="coerce")
        valid = parsed.dropna()
        if not valid.empty:
            return str(column), valid.min().date().isoformat(), valid.max().date().isoformat()
    return "", "", ""


def frame_record(path: Path, frame: pd.DataFrame, object_name: str = "") -> dict[str, object]:
    date_column, start, end = date_summary(frame)
    return {
        "path": str(path.resolve()),
        "format": path.suffix.lower().lstrip("."),
        "object": object_name,
        "rows": len(frame),
        "columns": json.dumps([str(column) for column in frame.columns], ensure_ascii=False),
        "date_column": date_column,
        "start_date": start,
        "end_date": end,
        "mapped_fields": ",".join(mapped_fields(frame.columns)),
        "notes": "",
    }


def inspect_file(path: Path) -> list[dict[str, object]]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            return [frame_record(path, pd.read_csv(path))]
        if suffix in {".xls", ".xlsx"}:
            book = pd.ExcelFile(path)
            return [
                frame_record(path, pd.read_excel(path, sheet_name=sheet), str(sheet))
                for sheet in book.sheet_names
            ]
        if suffix == ".parquet":
            return [frame_record(path, pd.read_parquet(path))]
        if suffix == ".feather":
            return [frame_record(path, pd.read_feather(path))]
        if suffix in {".db", ".sqlite", ".sqlite3"}:
            records: list[dict[str, object]] = []
            with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True) as connection:
                tables = pd.read_sql_query(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", connection
                )["name"]
                for table in tables:
                    quoted = str(table).replace('"', '""')
                    records.append(
                        frame_record(path, pd.read_sql_query(f'SELECT * FROM "{quoted}"', connection), str(table))
                    )
            return records
        return [
            {
                "path": str(path.resolve()),
                "format": suffix.lstrip("."),
                "object": "",
                "rows": "",
                "columns": "[]",
                "date_column": "",
                "start_date": "",
                "end_date": "",
                "mapped_fields": "",
                "notes": "Skipped: pickle is not deserialized during inventory",
            }
        ]
    except Exception as exc:  # inventory must record individual unreadable candidates
        return [
            {
                "path": str(path.resolve()),
                "format": suffix.lstrip("."),
                "object": "",
                "rows": "",
                "columns": "[]",
                "date_column": "",
                "start_date": "",
                "end_date": "",
                "mapped_fields": "",
                "notes": f"{type(exc).__name__}: {exc}",
            }
        ]


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Scan root is not a directory: {root}")
    records = [record for path in candidate_files(root) for record in inspect_file(path)]
    inventory = pd.DataFrame(records)
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        inventory.to_csv(output, index=False, encoding="utf-8-sig")
        print(f"WROTE: {output} ({len(inventory)} file objects)")
    else:
        print(inventory.to_csv(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
