"""Supplementary public-index interval comparison (not the strategy backtest)."""

from __future__ import annotations

import argparse
from pathlib import Path

import akshare as ak
import matplotlib.pyplot as plt
import pandas as pd


INDEX_MAP = {
    "399373": "大盘价值",
    "399372": "大盘成长",
    "399375": "中盘价值",
    "399374": "中盘成长",
    "399377": "小盘价值",
    "399376": "小盘成长",
    "399296": "创成长",
    "399295": "创价值",
}
ORDER = [
    "大盘价值", "大盘成长", "中盘价值", "中盘成长",
    "小盘价值", "小盘成长", "创价值", "创成长",
]


def fetch_interval_returns(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch the original eight public style indices and preserve its formula."""

    results: list[dict[str, object]] = []
    print(f"{'风格名称':<10} | {'起始收盘':<12} | {'结束收盘':<12} | 收益率")
    print("-" * 65)
    for ticker, name in INDEX_MAP.items():
        try:
            frame = ak.index_zh_a_hist(
                symbol=ticker,
                period="daily",
                start_date=start_date,
                end_date=end_date,
            )
            if frame is None or frame.empty:
                print(f"{name:<10} | 接口返回空数据")
                continue
            close_column = "收盘" if "收盘" in frame.columns else "close"
            start_value = float(frame[close_column].iloc[0])
            end_value = float(frame[close_column].iloc[-1])
            return_pct = ((end_value / start_value) - 1) * 100
            results.append({"风格标签": name, "收益率": return_pct})
            print(
                f"{name:<10} | {start_value:<14.2f} | {end_value:<14.2f} | "
                f"{return_pct:>7.2f}%"
            )
        except Exception as exc:  # Preserve the original per-index failure isolation.
            print(f"{name:<10} | 数据获取或解析失败: {exc}")
    result = pd.DataFrame(results)
    if not result.empty:
        result["风格标签"] = pd.Categorical(
            result["风格标签"], categories=ORDER, ordered=True
        )
        result = result.sort_values("风格标签", ascending=False)
    return result


def plot_interval_returns(
    result: pd.DataFrame,
    start_date: str,
    end_date: str,
    output: Path | None,
    show: bool,
) -> None:
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False
    figure, axis = plt.subplots(figsize=(10, 6))
    colors = ["#ff4d4f" if value > 0 else "#52c41a" for value in result["收益率"]]
    bars = axis.barh(result["风格标签"], result["收益率"], color=colors, height=0.6)
    for bar in bars:
        width = bar.get_width()
        axis.text(
            width + (0.2 if width >= 0 else -0.2),
            bar.get_y() + bar.get_height() / 2,
            f"{width:.2f}%",
            va="center",
            ha="left" if width >= 0 else "right",
            fontsize=10,
            fontweight="bold",
        )
    axis.axvline(0, color="black", linewidth=0.8)
    axis.set_title(f"风格指数区间表现 ({start_date} - {end_date})", fontsize=14, pad=20)
    figure.tight_layout()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(figure)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="20251231", help="YYYYMMDD")
    parser.add_argument("--end-date", default="20260227", help="YYYYMMDD")
    parser.add_argument("--output", type=Path, help="Optional plot path")
    parser.add_argument("--no-show", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = fetch_interval_returns(args.start_date, args.end_date)
    if result.empty:
        print("没有可用于绘图的真实接口数据。")
        return 1
    plot_interval_returns(result, args.start_date, args.end_date, args.output, not args.no_show)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
