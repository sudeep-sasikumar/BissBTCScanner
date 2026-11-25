"""Universe: WEEX contract classification, Binance history mapping, point-in-time tiers (section 4)."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

# WEEX labels a few index CFDs as "Stocks"
INDEX_OVERRIDES = {"US30USDT", "GER40USDT", "SP500USDT", "NAS100USDT", "HK50USDT", "KOSPIUSDT"}
STABLE_OR_WRAPPED = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "USDE", "USD1", "WBTC", "WETH", "BFUSD",
                     "XUSD", "USDS", "PYUSD", "RLUSD", "EUR", "EURI", "USTC"}


def classify(sym: dict) -> str:
    """crypto | stock | index | commodity | fx | other, from WEEX exchangeInfo fields."""
    if sym.get("contractType") == "PERPETUAL":
        return "crypto"
    if sym["symbol"] in INDEX_OVERRIDES:
        return "index"
    u = (sym.get("underlyingType") or "").lower()
    return {"stocks": "stock", "indices": "index", "metals": "commodity", "commodities": "commodity",
            "forex": "fx"}.get(u, "other")


NON_COIN_INDEXES = {"BTCDOMUSDT", "DEFIUSDT", "ALLUSDT", "FOOTBALLUSDT", "BLUEBIRDUSDT"}


def binance_symbol_for(base: str, asset_class: str, bn_symbols: set[str],
                       underlying: dict[str, str] | None = None) -> str | None:
    """Map a WEEX base asset to a Binance USDT-M symbol of the SAME asset class (same base; 1000x variants
    tried for crypto). Binance symbols missing from `underlying` (delisted, vision-only) count as COIN."""
    underlying = underlying or {}

    def ok(c: str) -> bool:
        if c not in bn_symbols or c in NON_COIN_INDEXES:
            return False
        u = underlying.get(c, "COIN")
        return (u == "COIN") == (asset_class == "crypto")

    cands = [f"{base}USDT"]
    if base.startswith("1000"):
        cands.append(f"{base[4:]}USDT")
    elif base.startswith("1M"):
        cands.append(f"{base[2:]}USDT")
    else:
        cands += [f"1000{base}USDT", f"1000000{base}USDT", f"1M{base}USDT"]
    if asset_class != "crypto":
        cands = cands[:1]
    for c in cands:
        if ok(c):
            return c
    return None


def is_holdout(base: str, frac: float, seed: int = 7) -> bool:
    """Deterministic symbol holdout (never used for design). T1 majors are never held out."""
    if base in {"BTC", "ETH"}:
        return False
    h = int(hashlib.sha256(f"{seed}:{base}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return h < frac


def point_in_time_ranks(daily_qv: pd.DataFrame, lookback: int = 30) -> pd.DataFrame:
    """daily_qv: index=date, columns=symbol, values=daily quote volume. Returns rank by trailing 30-day
    average volume, known as of the END of each day (use rank.shift(1) for decisions made during a day)."""
    avg = daily_qv.rolling(lookback, min_periods=lookback // 2).mean()
    return avg.rank(axis=1, ascending=False, method="first")


def tier_table(daily_qv: pd.DataFrame, t1: list[str], base_of: dict[str, str], top_n: int, floor: float,
               lookback: int = 30) -> pd.DataFrame:
    """Per day x symbol tier label ('T1','T2','T3' or ''), point-in-time, shifted one day (no lookahead)."""
    ranks = point_in_time_ranks(daily_qv, lookback).shift(1)
    med = daily_qv.rolling(lookback, min_periods=lookback // 2).median().shift(1)
    tiers = pd.DataFrame("", index=daily_qv.index, columns=daily_qv.columns)
    is_t1 = np.array([base_of.get(c, c) in t1 for c in daily_qv.columns])
    r = ranks.to_numpy()
    m = med.to_numpy()
    out = np.full(r.shape, "", dtype=object)
    out[(r <= top_n)] = "T2"
    out[(r > top_n) & (m >= floor)] = "T3"
    out[:, is_t1] = np.where(np.isnan(r[:, is_t1]), "", "T1")
    tiers[:] = out
    return tiers
