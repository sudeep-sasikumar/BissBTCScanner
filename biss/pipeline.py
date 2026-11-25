"""Per-symbol pipeline: data -> raw signals -> exit simulation for every management variant."""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config
from .data import binance
from .data.resolve1m import Resolver
from .setups import NS_15M, generate, make_bars
from .tiers import base_of, tier_on
from .trade import MGMT, simulate

DEFAULT_TAKER, DEFAULT_MAKER = 0.0008, 0.0002  # WEEX's standard rates (exchangeInfo, 2026-11-25)


@lru_cache(maxsize=1)
def weex_map() -> dict:
    cfg = config.load()
    u = pd.read_csv(config.ROOT / "reports" / "universe.csv")
    out = {}
    for _, r in u[u.binance_symbol.notna()].iterrows():
        out[r.binance_symbol] = {"weex_symbol": r.symbol, "asset_class": r.asset_class, "taker": r.taker_fee,
                                 "maker": r.maker_fee, "weex_max_lev": r.max_leverage}
    return out


def load_symbol(sym: str, cfg):
    st = binance.Store(config.data_dir(cfg))
    daily = st.load(sym, "1d")
    m15 = st.load(sym, "15m")
    fp = config.data_dir(cfg) / "binance" / "funding" / f"{sym}.parquet"
    fund = pd.read_parquet(fp)["rate"] if fp.exists() else pd.Series(dtype=float)
    return daily, m15, fund


def run_symbol(sym: str, cfg=None, variants=("R1", "R2", "R3d", "R3w"), entries=("E1", "E2"),
               mgmts=MGMT, sides=(1, -1), use_1m: bool = True, tag: str = "main") -> pd.DataFrame:
    cfg = cfg or config.load()
    daily, m15, fund = load_symbol(sym, cfg)
    if daily.empty or m15.empty or len(daily) < 120:
        return pd.DataFrame()
    m15 = m15[~m15.index.duplicated()].sort_index()
    # bars with a zero close (rare data glitches) break percentage maths
    m15 = m15[(m15["close"] > 0) & (m15["low"] > 0)]
    sig = generate(sym, m15, daily, cfg, cfg.data.start, variants, entries, sides)
    if sig.empty:
        return sig
    wm = weex_map().get(sym, {})
    asset_class = wm.get("asset_class", "crypto")
    taker = float(wm.get("taker", DEFAULT_TAKER) or DEFAULT_TAKER)
    maker = float(wm.get("maker", DEFAULT_MAKER) or DEFAULT_MAKER)
    ft = fund.index.as_unit("ns").asi8 if len(fund) else np.array([], dtype="int64")
    fr = fund.to_numpy(float) if len(fund) else np.array([])
    res = Resolver(config.data_dir(cfg), sym) if use_1m else None
    bars = {1: make_bars(m15, 1, cfg.sweep.atr_len), -1: make_bars(m15, -1, cfg.sweep.atr_len)}
    out = []
    for _, s in sig.iterrows():
        d = s.to_dict()
        d.update({"base": base_of(sym), "asset_class": asset_class, "weex_symbol": wm.get("weex_symbol", ""),
                  "on_weex": bool(wm), "taker": taker, "maker": maker, "tag": tag,
                  "weex_max_lev": wm.get("weex_max_lev", np.nan)})
        if d.get("skipped"):
            out.append(d)
            continue
        tier = tier_on(sym, d["entry_time"]) if asset_class == "crypto" else "T4"
        d["tier"] = tier
        if not tier:
            d["skipped"] = "no_tier"
            out.append(d)
            continue
        slip = float(cfg.costs.slippage[tier])
        sign = 1 if d["side"] == "long" else -1
        b = bars[sign]
        ke = int(d["entry_idx"])
        e, stp = sign * d["entry"], sign * d["stop"]
        tp1, tp2 = sign * d["tp1_eff"], sign * d["tp2"]
        L = sign * d["level"]
        resolver = res.make(sign) if res else None
        for m in mgmts:
            r = simulate(b, ke, e, stp, tp1, tp2, L, m, taker, maker, slip, resolver, ft, fr,
                         cfg.management.time_stop_days)
            for k, v in r.items():
                d[f"{k}_{m}"] = v
        out.append(d)
    df = pd.DataFrame(out)
    if res:
        df["n_1m_calls"] = res.calls
        df["n_1m_missing"] = res.missing
    return df
