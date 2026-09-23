"""
Demo: Factor neutralization (industry + style) -> pure alpha score (residual).

Goal (per your spec):
  Input: raw factor value Factor_raw(i,t)  (example: 20-day momentum)
  Regressors: SW L1 (2021) one-hot + Style(Beta vs 000985.SH, Size, Volatility, Liquidity)
  Output: residual epsilon(i,t) as Pure Alpha score

Backtest (toy; retained for research provenance and never called by run_replication.py):
  Each day pick Top 50 by pure alpha, equal-weight, hold next day.

This file is incomplete research code. Its fallback market proxy and toy PnL
must not be presented as the paper's production strategy or replication result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm

import panda_data
from panda_common.config import get_config
from panda_common.handlers.database_handler import DatabaseHandler


@dataclass(frozen=True)
class NeutralizeConfig:
    start_date: str
    end_date: str
    universe_indicator: str = "000985"  # use broad universe
    include_st: bool = True
    beta_window: int = 252
    vol_window: int = 252
    liq_window: int = 20  # rolling mean turnover
    mom_window: int = 20  # raw factor window
    top_n: int = 50


def _winsorize(s: pd.Series, p: float = 0.01) -> pd.Series:
    lo = s.quantile(p)
    hi = s.quantile(1 - p)
    return s.clip(lo, hi)


def _zscore(s: pd.Series) -> pd.Series:
    std = s.std(ddof=0)
    if std == 0 or np.isnan(std):
        return s * 0.0
    return (s - s.mean()) / std


def _prepare_index_returns(db: DatabaseHandler, mongo_db: str, start_date: str, end_date: str) -> pd.Series:
    rec = db.mongo_find(mongo_db, "index_daily", {"symbol": "000985.SH", "date": {"$gte": start_date, "$lte": end_date}})
    if not rec:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rec)
    df = df.sort_values("date")
    df["ret"] = df["close"] / df["pre_close"] - 1
    return df.set_index("date")["ret"].astype(float)


def _load_sw_industry(db: DatabaseHandler, mongo_db: str) -> pd.DataFrame:
    rec = db.mongo_find(mongo_db, "sw_industry_l1_2021", {}, projection={"_id": 0})
    if not rec:
        raise RuntimeError("sw_industry_l1_2021 is empty; run scripts/ts_clean_sw_industry_2021.py first")
    df = pd.DataFrame(rec).dropna(subset=["symbol", "industry_l1_name"])
    return df[["symbol", "industry_l1_name"]].drop_duplicates("symbol")


def compute_style_exposures(
    mkt: pd.DataFrame,
    base: pd.DataFrame,
    index_ret: pd.Series,
    cfg: NeutralizeConfig,
) -> pd.DataFrame:
    """
    Returns DataFrame indexed by (date,symbol) with columns: beta,size,vol,liq
    """
    mkt = mkt.sort_values(["symbol", "date"]).copy()
    mkt["ret"] = mkt["close"] / mkt["pre_close"] - 1

    # rolling beta (cov(ret, idx)/var(idx))
    def _beta(g: pd.DataFrame) -> pd.Series:
        r = g.set_index("date")["ret"].reindex(index_ret.index)
        # align and compute rolling covariance
        cov = r.rolling(cfg.beta_window).cov(index_ret)
        var = index_ret.rolling(cfg.beta_window).var()
        b = cov / var
        return b.reindex(g["date"]).to_numpy()

    mkt["beta"] = mkt.groupby("symbol", group_keys=False).apply(_beta)

    # volatility: rolling std of stock returns
    mkt["vol"] = (
        mkt.groupby("symbol")["ret"]
        .rolling(cfg.vol_window)
        .std(ddof=0)
        .reset_index(level=0, drop=True)
    )

    # join size/liquidity from factor_base (market_cap, turnover)
    base = base.copy()
    keep = ["date", "symbol", "market_cap", "turnover"]
    base = base[keep]
    df = pd.merge(mkt[["date", "symbol", "beta", "vol"]], base, on=["date", "symbol"], how="left")

    df["size"] = np.log(df["market_cap"].replace({0: np.nan}))
    df["liq"] = (
        df.sort_values(["symbol", "date"])
        .groupby("symbol")["turnover"]
        .rolling(cfg.liq_window)
        .mean()
        .reset_index(level=0, drop=True)
    )
    return df.set_index(["date", "symbol"])[["beta", "size", "vol", "liq"]]


def compute_raw_factor_mom20(mkt: pd.DataFrame, cfg: NeutralizeConfig) -> pd.DataFrame:
    """
    20D momentum: close/lag(close,20)-1
    """
    mkt = mkt.sort_values(["symbol", "date"]).copy()
    mkt["mom20"] = mkt.groupby("symbol")["close"].pct_change(cfg.mom_window)
    return mkt.set_index(["date", "symbol"])[["mom20"]]


def neutralize_cross_section(
    factor_raw: pd.Series,
    style: pd.DataFrame,
    industry: pd.Series,
) -> pd.Series:
    """
    For one date: y=factor_raw; X=[style + industry dummies]; output residuals.
    """
    df = pd.concat([factor_raw.rename("y"), style, industry.rename("industry")], axis=1)
    df = df.dropna()
    if df.empty or df.shape[0] < 50:
        return pd.Series(dtype=float)

    y = _winsorize(df["y"])
    y = _zscore(y)

    Xs = df[["beta", "size", "vol", "liq"]].apply(_winsorize).apply(_zscore)
    ind = pd.get_dummies(df["industry"], prefix="ind", drop_first=True)
    X = pd.concat([Xs, ind], axis=1)
    X = sm.add_constant(X, has_constant="add")

    model = sm.OLS(y, X, missing="drop")
    res = model.fit()
    eps = res.resid
    return eps.rename("alpha_score")


def run_demo(cfg: NeutralizeConfig) -> Tuple[pd.DataFrame, pd.DataFrame]:
    panda_data.init()
    config = get_config()
    db = DatabaseHandler(config)

    # market data (need close, pre_close)
    mkt = panda_data.get_market_data(
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        indicator=cfg.universe_indicator,
        st=cfg.include_st,
        fields=["open", "close", "high", "low", "pre_close", "limit_up", "limit_down", "name"],
    )
    if mkt is None or mkt.empty:
        raise RuntimeError("stock_market empty for date range; run panda_data_hub stock_market cleaning first")

    # factor_base data for size/liquidity
    base = panda_data.get_factor(
        factors=["market_cap", "turnover"],
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        index_component=None,
        type="stock",
    )
    if base is None or base.empty:
        raise RuntimeError("factor_base empty for date range; run panda_data_hub factor_base cleaning first")

    idx_ret = _prepare_index_returns(db, config["MONGO_DB"], cfg.start_date, cfg.end_date)
    if idx_ret.empty:
        # Permission-friendly fallback: proxy market return by value-weighted stock returns.
        tmp = mkt[["date", "symbol", "close", "pre_close"]].copy()
        tmp["ret"] = tmp["close"] / tmp["pre_close"] - 1
        w = base[["date", "symbol", "market_cap"]].copy()
        vw = tmp.merge(w, on=["date", "symbol"], how="left").dropna(subset=["ret", "market_cap"])
        vw["market_cap"] = vw["market_cap"].clip(lower=0)
        idx_ret = vw.groupby("date", sort=True).apply(
            lambda g: float(np.average(g["ret"].to_numpy(), weights=g["market_cap"].to_numpy()))
        )
        idx_ret.name = "ret"
    sw = _load_sw_industry(db, config["MONGO_DB"])

    # industry series indexed by (date,symbol) via static map
    m = mkt[["date", "symbol"]].drop_duplicates()
    m = m.merge(sw, on="symbol", how="left")
    industry = m.set_index(["date", "symbol"])["industry_l1_name"]

    raw = compute_raw_factor_mom20(mkt, cfg)["mom20"]
    style = compute_style_exposures(mkt, base, idx_ret, cfg)

    # neutralize by date
    out = []
    for d, y in raw.groupby(level=0):
        eps = neutralize_cross_section(
            factor_raw=y.droplevel(0),
            style=style.xs(d).copy() if d in style.index.get_level_values(0) else pd.DataFrame(),
            industry=industry.xs(d) if d in industry.index.get_level_values(0) else pd.Series(dtype=object),
        )
        if not eps.empty:
            eps.index = pd.MultiIndex.from_product([[d], eps.index], names=["date", "symbol"])
            out.append(eps)
    alpha = pd.concat(out).to_frame()

    # toy backtest: next-day return = close(t+1)/close(t)-1
    mkt2 = mkt.sort_values(["symbol", "date"]).copy()
    mkt2["ret_fwd1"] = mkt2.groupby("symbol")["close"].shift(-1) / mkt2["close"] - 1
    ret_fwd = mkt2.set_index(["date", "symbol"])["ret_fwd1"]

    daily_pnl = []
    for d in sorted(alpha.index.get_level_values(0).unique()):
        s = alpha.xs(d)["alpha_score"].dropna()
        if s.empty:
            continue
        pick = s.nlargest(cfg.top_n).index
        r = ret_fwd.xs(d).reindex(pick).dropna()
        if r.empty:
            continue
        daily_pnl.append({"date": d, "ret": float(r.mean())})
    bt = pd.DataFrame(daily_pnl).sort_values("date")
    if not bt.empty:
        bt["nav"] = (1 + bt["ret"]).cumprod()

    return alpha.reset_index(), bt


if __name__ == "__main__":
    cfg = NeutralizeConfig(start_date="20220101", end_date="20251231")
    alpha, bt = run_demo(cfg)
    print(alpha.head())
    print(bt.tail())
