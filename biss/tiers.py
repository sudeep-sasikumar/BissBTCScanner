"""Point-in-time tiers for crypto (Binance volume ranks) and TradeFi (T4)."""
from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from . import config
from .universe import STABLE_OR_WRAPPED, tier_table


def base_of(sym: str) -> str:
    b = sym[:-4] if sym.endswith("USDT") else sym
    for pre in ("1000000", "1000", "1M"):
        if b.startswith(pre) and len(b) > len(pre) + 1:
            return b[len(pre):]
    return b


@lru_cache(maxsize=1)
def crypto_tiers() -> pd.DataFrame:
    cfg = config.load()
    dd = config.data_dir(cfg) / "binance"
    q = pd.read_parquet(dd / "daily_qv.parquet")
    meta = json.loads((dd / "symbols.json").read_text(encoding="utf-8"))
    und = meta["underlying"]
    cols = [c for c in q.columns if und.get(c, "COIN") == "COIN" and base_of(c) not in STABLE_OR_WRAPPED]
    q = q[cols]
    u = cfg.universe
    return tier_table(q, list(u.t1), {c: base_of(c) for c in cols}, u.t2_top_n, u.liquidity_floor_usd,
                      u.rank_lookback_days)


def tier_on(sym: str, day: pd.Timestamp) -> str:
    t = crypto_tiers()
    if sym not in t.columns:
        return ""
    d = day.normalize()
    if d not in t.index:
        return ""
    return t.at[d, sym]
