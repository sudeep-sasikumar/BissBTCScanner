"""Baselines (section 8.4).

1. Refined weekly rules (docs/bissbtc-x-framework-strategy-research.md, "Refined rules"):
   weekly pivot level (2 bars each side, >= max(20%, 2.5x median weekly range) move within 10 weeks),
   swept low 30-50% below the 120-day high, weekly low below the level then a weekly close back above within
   3 weeks (entry at that weekly close), BTC not in a bull regime, no FOMC within 7 days, stop 1% below the
   swept low, 50% off at +1R, stop to entry, rest to the prior 120-day high. Simulated on daily bars, stop
   before target. Documented result: 158 trades, 68% win, +0.97R (point-in-time top 50, fees 0.05%/side).
2. Rule C (4h challenge style, docs/bissbtc-scanner-6m-study-2026-10-28.md): built on the 15m engine with a
   config override (daily+weekly pivots, R2 4h reclaim within 24h, stop 0.3 ATR(4h), no acceptance rule).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import calendar as cal
from .indicators import resample
from .levels import pivots
from .setups import NS_D, Bars
from .trade import simulate

NS_W = 7 * NS_D


def daily_bars(daily: pd.DataFrame) -> Bars:
    t = daily.index.as_unit("ns").asi8
    close_t = t + NS_D
    n = len(t)
    return Bars(t, daily["open"].to_numpy(), daily["high"].to_numpy(), daily["low"].to_numpy(),
                daily["close"].to_numpy(), np.zeros(n), np.zeros(n), np.zeros(n, bool), np.ones(n, bool),
                ((close_t - 4 * NS_D) % NS_W) == 0, 1, NS_D)


def refined_weekly(sym: str, daily: pd.DataFrame, btc_bull: pd.Series, start: str, fee: float = 0.0005,
                   maker: float | None = None, dd_band=(0.30, 0.50), window_weeks: int = 3,
                   use_regime: bool = True, use_fomc: bool = True, daily_sweep: bool = False,
                   kinds=("pivot_low", "pivot_high"), slip: float = 0.0, funding_8h: float = 0.0,
                   min_move: float = 0.20, earnings: list | None = None) -> list[dict]:
    w = resample(daily, "W")
    if len(w) < 20:
        return []
    lv = pivots(w, "W", 2, min_move, 2.5, 10, 52)
    if not lv:
        return []
    lv = pd.DataFrame(lv)
    lv = lv[lv["kind"].isin(kinds)]
    b = daily_bars(daily)
    didx = daily.index
    start_ts = pd.Timestamp(start, tz="UTC")
    out = []
    busy_until = pd.Timestamp(0, tz="UTC")
    bars = w if not daily_sweep else daily
    period = pd.Timedelta(days=7) if not daily_sweep else pd.Timedelta(days=1)
    win = window_weeks if not daily_sweep else 14
    bi = bars.index
    for i in range(1, len(bars)):
        t = bi[i]
        if t < start_ts or t < busy_until:
            continue
        act = lv[lv["valid_from"] <= t]
        pc, lo = bars["close"].iloc[i - 1], bars["low"].iloc[i]
        cand = act[(act["price"] < pc) & (act["price"] > lo)]
        if cand.empty:
            continue
        L = float(cand["price"].max())
        for j in range(i, min(i + win, len(bars))):
            if bars["close"].iloc[j] > L:
                swept = float(bars["low"].iloc[i: j + 1].min())
                entry_t = bi[j] + period  # bar close
                prior = daily[(didx < bi[i] + period) & (didx >= bi[i] + period - pd.Timedelta(days=120))]
                hi120 = float(prior["high"].max())
                dd = 1 - swept / hi120
                ke = int(didx.searchsorted(entry_t)) - 1
                if ke < 0 or ke >= len(didx) - 1:
                    break
                entry = float(daily["close"].iloc[ke])
                stop = swept * 0.99
                ok_dd = dd_band[0] <= dd <= dd_band[1]
                day = entry_t.normalize() - pd.Timedelta(days=1)
                bull = bool(btc_bull.get(day, False))
                fomc = cal.near_fomc(entry_t, 7)
                rec = {"symbol": sym, "entry_time": entry_t, "level": L, "swept_low": swept, "entry": entry,
                       "stop": stop, "stop_pct": (entry - stop) / entry, "tp2": hi120, "dd_from_120d": dd,
                       "btc_bull": bull, "near_fomc": fomc, "f_dd": ok_dd}
                if entry <= stop or hi120 <= entry:
                    break
                ft = fr = None
                if funding_8h:
                    ft = np.arange(b.t[ke], b.t[-1] + NS_D, 8 * 3600 * 10**9, dtype=np.int64)
                    fr = np.full(len(ft), funding_8h)
                r = simulate(b, ke, entry, stop, entry + (entry - stop), hi120, L, "partial_1r_be", fee,
                             maker if maker is not None else fee, slip, None, ft, fr)
                rec.update({k: v for k, v in r.items()})
                rec["exit_time"] = pd.Timestamp(r["exit_time_ns"], tz="UTC")
                keep = ok_dd and (not use_regime or not bull) and (not use_fomc or not fomc)
                rec["kept"] = keep
                out.append(rec)
                if keep:
                    busy_until = rec["exit_time"]
                break
    return out


RULE_C_OVERRIDES = {
    "levels.daily_pivots": {"pivot_bars": 3, "min_move_pct": 0.12, "k_median_range": 4.0, "validate_within": 20},
    "levels.pivots_only": True,
    "reclaim.window_hours": 24,
    "stop.buffer_pct": 0.0,
    "sweep.max_atr1d": 1e9,
    "sweep.max_days_below": 10**6,
    "entry.max_attempts": 1,
}
