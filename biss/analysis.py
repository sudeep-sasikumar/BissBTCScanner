"""Turn raw signals into filtered, de-duplicated trade sets and the section-8 validation tables."""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config
from .data import binance
from .indicators import btc_regime
from .portfolio import cluster_of
from .sizing import lev_cap, mmr_for
from .universe import is_holdout

FILTERS = ["F1_regime", "F2_drawdown", "F3_fomc", "F3_qclose", "F4_location", "stop_max", "min_rr"]


@lru_cache(maxsize=1)
def brackets() -> dict:
    cfg = config.load()
    p = config.data_dir(cfg) / "weex" / "brackets.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_signals(tag: str = "main") -> pd.DataFrame:
    cfg = config.load()
    d = config.data_dir(cfg) / "signals" / tag
    parts = [pd.read_parquet(p) for p in sorted(d.glob("*.parquet"))]
    parts = [p for p in parts if not p.empty]
    df = pd.concat(parts, ignore_index=True)
    for c in ("entry_time", "swept_time", "reclaim_time", "sweep_start"):
        if c in df:
            df[c] = pd.to_datetime(df[c], utc=True)
    return df


def enrich(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """Add regime, filter flags, tiers, risk multipliers and leverage needs."""
    df = df[df["skipped"].fillna("") == ""].copy()
    st = binance.Store(config.data_dir(cfg))
    btc = st.load("BTCUSDT", "1d")
    bull = btc_regime(btc, cfg.filters.regime_flip_days)
    day = (df["entry_time"].dt.floor("D") - pd.Timedelta(days=1))
    df["btc_bull"] = day.map(bull).fillna(False).astype(bool)
    f = cfg.filters
    tradfi = df["asset_class"] != "crypto"
    lo = np.where(tradfi, f.dd_tradfi[0], f.dd_crypto[0])
    hi = np.where(tradfi, f.dd_tradfi[1], f.dd_crypto[1])
    df["F1_regime"] = ~df["btc_bull"] | tradfi
    df["F2_drawdown"] = (df["dd_from_120d"] >= lo) & (df["dd_from_120d"] <= hi)
    df["F3_fomc"] = df["days_to_fomc"].abs() > f.fomc_days
    df["F3_qclose"] = df["days_to_qclose"] > f.quarter_close_days
    df["F4_location"] = df["f_location"].astype(bool)
    df["stop_max"] = df["f_stop_ok"].astype(bool)
    df["min_rr"] = df["f_rr_ok"].astype(bool)
    df["holdout"] = df["base"].map(lambda b: is_holdout(b, cfg.validation.holdout_frac, cfg.validation.seed))
    split = pd.Timestamp(cfg.validation.split_date, tz="UTC")
    df["slice"] = np.where(df["holdout"], "HO", np.where(df["entry_time"] < split, "IS", "OOS"))
    df["year"] = df["entry_time"].dt.year
    strong = (df["pivot_tf"] == "M") | ((df["pivot_tf"] == "W") & df["F1_regime"] & df["F2_drawdown"])
    mult = np.where(strong, cfg.sizing.tier_mult.strong, cfg.sizing.tier_mult.weekly_only)
    mult = np.where(df["side"] == "short", mult * cfg.sizing.tier_mult.short, mult)
    mult = np.where(tradfi, mult * cfg.sizing.tier_mult.tradfi, mult)
    df["risk_mult"] = mult
    df["conviction"] = np.where(strong, "strong", "weekly_only")
    br = brackets()
    caps = dict(cfg.sizing.lev_caps)
    caps["tradfi"] = caps.get("tradfi", 3)
    df["lev_cap"] = [lev_cap(b, a, caps, int(m) if pd.notna(m) else None)
                     for b, a, m in zip(df["base"], df["asset_class"], df["weex_max_lev"])]
    mmr = np.array([mmr_for(br.get(w), 1e4)[0] for w in df["weex_symbol"]])
    df["lev_needed"] = 1.0 / ((1 + cfg.sizing.liq_buffer_mult) * df["stop_pct"] + mmr)
    df["at_cap"] = df["lev_needed"] > df["lev_cap"]
    df["cluster"] = [cluster_of(b, a) for b, a in zip(df["base"], df["asset_class"])]
    return df


def trades(df: pd.DataFrame, mgmt: str = "partial_1r_be", reclaim: str | None = None, entry: str | None = None,
           side: str = "long", filters: list[str] | None = None, tiers: list[str] | None = None,
           attempts: int = 2) -> pd.DataFrame:
    """Filter, then keep one position per symbol & side at a time (first entry wins)."""
    filters = FILTERS if filters is None else filters
    m = pd.Series(True, index=df.index)
    if reclaim:
        m &= df["reclaim_variant"] == reclaim
    if entry:
        m &= df["entry_variant"] == entry
    if side:
        m &= df["side"] == side
    if tiers:
        m &= df["tier"].isin(tiers)
    m &= df["attempt"] <= attempts
    for f in filters:
        m &= df[f]
    t = df[m].copy()
    t["R"] = t[f"R_{mgmt}"]
    t["exit_time"] = pd.to_datetime(t[f"exit_time_ns_{mgmt}"], utc=True)
    for c in ("outcome", "hold_days", "fees_frac", "funding_frac", "mae_frac", "exit_price"):
        t[c] = t[f"{c}_{mgmt}"]
    t = t.sort_values("entry_time")
    keep, busy = [], {}
    for i, sym, sd, et, xt in zip(t.index, t["symbol"], t["side"], t["entry_time"], t["exit_time"]):
        k = (sym, sd)
        if k in busy and busy[k] > et:
            continue
        busy[k] = xt
        keep.append(i)
    return t.loc[keep]
