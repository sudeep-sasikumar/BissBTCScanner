"""Sections 5.2-5.7: sweep -> reclaim -> entry on 15m bars, per symbol.

Shorts reuse the long logic in negated price space (p -> -p): "below the level" becomes "above", highs become
lows. Percentages always use real (absolute) prices.

Output: one row per (setup, reclaim variant, entry variant, attempt) with all filter flags attached but NOT
applied, so ablations are a post-hoc boolean mask. Exits are simulated in trade.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import calendar as cal
from .indicators import atr, resample
from .levels import LevelSet, build_levels, level_type

NS_15M = 15 * 60 * 10**9
NS_H = 3600 * 10**9
NS_D = 86400 * 10**9


@dataclass
class Bars:
    """15m arrays in direction space (sign=+1 long, -1 short)."""
    t: np.ndarray        # open time ns
    o: np.ndarray
    h: np.ndarray        # 'adverse-side' extreme is lo; favourable is hi (in direction space)
    lo: np.ndarray
    c: np.ndarray
    atr4: np.ndarray     # ATR(4h) as of the last completed 4h bar (absolute)
    atr1d: np.ndarray    # ATR(1d) as of the previous day close (absolute)
    is4h: np.ndarray     # bar closes a 4h candle
    isday: np.ndarray    # bar closes a UTC day
    iswk: np.ndarray     # bar closes a week (Sun 23:45)
    sign: int
    bar_ns: int = NS_15M


def make_bars(m15: pd.DataFrame, sign: int, atr_len: int) -> Bars:
    h4 = resample(m15, "4h")
    d1 = resample(m15, "1D")
    a4 = atr(h4, atr_len).shift(1).reindex(m15.index, method="ffill").to_numpy()
    a1 = atr(d1, atr_len).shift(1).reindex(m15.index, method="ffill").to_numpy()
    t = m15.index.as_unit("ns").asi8
    close_t = t + NS_15M
    is4h = (close_t % (4 * NS_H)) == 0
    isday = (close_t % NS_D) == 0
    # weeks start Monday 00:00 UTC; epoch (Thu 1970-01-01) -> Monday 1970-01-05 = 4 days offset
    iswk = ((close_t - 4 * NS_D) % (7 * NS_D)) == 0
    if sign > 0:
        o, h, lo, c = (m15[k].to_numpy() for k in ("open", "high", "low", "close"))
    else:
        o, h, lo, c = (-m15["open"].to_numpy(), -m15["low"].to_numpy(), -m15["high"].to_numpy(),
                       -m15["close"].to_numpy())
    return Bars(t, o, h, lo, c, a4, a1, is4h, isday, iswk, sign)


def _first(mask: np.ndarray, start: int = 0) -> int:
    """first index >= start where mask is True, else -1"""
    if start >= len(mask):
        return -1
    i = int(np.argmax(mask[start:]))
    return start + i if mask[start + i] else -1


def find_reclaim(b: Bars, L: float, k0: int, variant: str, cfg, horizon: int) -> tuple[str, int, int]:
    """From sweep start k0, return (event, index, swept_low_index); event in reclaim|accept|expire|none.
    L is in direction space. swept low = running min of lo since k0."""
    sw = cfg.sweep
    end = min(len(b.t), k0 + horizon)
    lo = b.lo[k0:end]
    cm = np.minimum.accumulate(lo)
    newmin = np.r_[True, lo[1:] < cm[:-1]]
    lowidx = np.maximum.accumulate(np.where(newmin, np.arange(len(lo)), 0)) + k0
    seg = slice(k0, end)
    t = b.t[seg]
    # acceptance 1: depth beyond sweep_max * ATR(daily)
    acc1 = cm < L - sw.max_atr1d * np.nan_to_num(b.atr1d[seg], nan=np.inf)
    # acceptance 2: more than max_days_below daily closes below L
    below_day = b.isday[seg] & (b.c[seg] < L)
    acc2 = np.cumsum(below_day) > sw.max_days_below
    acc = acc1 | acc2
    if variant in ("R1", "R2"):
        win = (t - b.t[lowidx]) <= cfg.reclaim.window_hours * NS_H
    else:
        win = (t - b.t[k0]) <= cfg.reclaim.r3_window_weeks * 7 * NS_D
    ca = b.c[seg] > L
    if variant == "R1":
        n = cfg.reclaim.r1_n_closes
        run = np.convolve(ca.astype(int), np.ones(n, dtype=int), "full")[: len(ca)]
        rec = run >= n
    elif variant == "R2":
        rec = ca & b.is4h[seg]
    elif variant == "R3d":
        rec = ca & b.isday[seg]
    elif variant == "R3w":
        rec = ca & b.iswk[seg]
    else:
        raise ValueError(variant)
    r = _first(rec & win & ~acc)
    a = _first(acc)
    e = _first(~win)
    cands = [(x, ev) for x, ev in ((r, "reclaim"), (a, "accept"), (e, "expire")) if x >= 0]
    if not cands:
        return "none", -1, -1
    x, ev = min(cands)
    return ev, k0 + x, int(lowidx[x])


def e2_entry(b: Bars, L: float, r: int, swept: float, expire_bars: int) -> int:
    """E2: first 15m pullback after the reclaim that holds above L (higher low), entry on the first close back
    above the pullback bar's high. Returns entry bar index or -1."""
    end = min(len(b.t), r + 1 + expire_bars)
    pb_high = None
    for k in range(r + 1, end):
        if b.lo[k] <= L or b.c[k] < L:
            return -1
        if pb_high is None:
            if b.c[k] < b.c[k - 1]:
                pb_high = b.h[k]
        else:
            if b.c[k] > pb_high:
                return k
            if b.c[k] < b.c[k - 1]:
                pb_high = b.h[k]
    return -1


def _stop(b: Bars, k: int, swept: float, cfg) -> float:
    """swept low minus max(0.3*ATR(4h), 1% of price), in direction space."""
    a4 = b.atr4[k] if np.isfinite(b.atr4[k]) else 0.0
    return swept - max(cfg.stop.buffer_atr4h * a4, cfg.stop.buffer_pct * abs(swept))


def generate(symbol: str, m15: pd.DataFrame, daily: pd.DataFrame, cfg, start: str,
             variants=("R1", "R2", "R3d", "R3w"), entries=("E1", "E2"), sides=(1, -1)) -> pd.DataFrame:
    """All raw signals for one symbol. `daily` is full-history daily bars (levels + context);
    `m15` covers the signal period plus warmup."""
    levels = build_levels(daily, cfg)
    if levels.empty or m15.empty:
        return pd.DataFrame()
    ls = LevelSet(levels)
    D = DailyArrays(daily)
    rows = []
    start_ns = pd.Timestamp(start, tz="UTC").value
    t15 = m15.index.as_unit("ns").asi8
    lvcfg = cfg.levels
    horizon_r12 = 30 * 96
    horizon_r3 = (cfg.reclaim.r3_window_weeks * 7 + 1) * 96
    day_ids = np.nonzero((D.t >= start_ns) & (D.t <= t15[-1]))[0]
    for sign in sides:
        b = make_bars(m15, sign, cfg.sweep.atr_len)
        busy_until: dict[tuple, int] = {}  # (zone price, variant, entry) -> bar index the setup ended
        for di in day_ids:
            if di < 1:
                continue
            d_ns = int(D.t[di])
            prev_close = D.c[di - 1]
            act = ls.active(d_ns)
            if sign > 0:
                cmask = act & (ls.price < prev_close) & (ls.price > D.l[di])
            else:
                cmask = act & (ls.price > prev_close) & (ls.price < D.h[di])
            if not cmask.any():
                continue
            near = act & (ls.price > prev_close * (1 - lvcfg.max_level_dist_pct)) & \
                (ls.price < prev_close * (1 + lvcfg.max_level_dist_pct))
            k_day = int(np.searchsorted(t15, d_ns))
            k_day_end = int(np.searchsorted(t15, d_ns + NS_D))
            if k_day >= len(t15):
                continue
            lo60 = D.l[max(0, di - lvcfg.location_lookback_days): di].min()
            hi60 = D.h[max(0, di - lvcfg.location_lookback_days): di].max()
            seen = set()
            for p in np.unique(ls.price[cmask & near]):
                z = ls.zone_of(p, near, lvcfg.merge_pct)
                Lr = z["price"]
                if Lr in seen:
                    continue
                seen.add(Lr)
                L = sign * Lr
                for variant in variants:
                    for entry_v in entries:
                        key = (Lr, variant, entry_v)
                        if busy_until.get(key, -1) >= k_day:
                            continue
                        res = _run_setup(symbol, b, L, Lr, z, k_day, k_day_end, variant, entry_v, cfg,
                                         horizon_r3 if variant.startswith("R3") else horizon_r12)
                        if not res:
                            continue
                        end_k, sigs = res
                        busy_until[key] = end_k
                        for s in sigs:
                            s.update(_context(s, D, ls, sign, lo60, hi60, cfg))
                            rows.append(s)
    return pd.DataFrame(rows)


class DailyArrays:
    def __init__(self, daily: pd.DataFrame):
        self.t = daily.index.as_unit("ns").asi8
        self.h = daily["high"].to_numpy(float)
        self.l = daily["low"].to_numpy(float)
        self.c = daily["close"].to_numpy(float)

    def before(self, t_ns: int) -> int:
        """number of daily bars that opened before t_ns's UTC day"""
        return int(np.searchsorted(self.t, (t_ns // NS_D) * NS_D))

    def touches(self, price: float, since_ns: int, until_ns: int, tol: float):
        a, b = int(np.searchsorted(self.t, since_ns)), int(np.searchsorted(self.t, until_ns))
        hit = np.nonzero((self.l[a:b] <= price * (1 + tol)) & (self.h[a:b] >= price * (1 - tol)))[0]
        if not len(hit):
            return 0, None
        tt = self.t[a:b][hit]
        return int((np.diff(tt) > 3 * NS_D).sum()) + 1, pd.Timestamp(int(tt[-1]), tz="UTC")


def _run_setup(symbol, b: Bars, L, Lr, z, k_day, k_day_end, variant, entry_v, cfg, horizon):
    """State machine for one level episode starting on day k_day. Returns (end_index, [signals])."""
    sw = cfg.sweep
    # sweep start: first bar today trading below L by >= sweep_min * ATR(4h)
    smin = sw.min_atr4h * np.nan_to_num(b.atr4[k_day:k_day_end], nan=np.inf)
    hits = np.nonzero(b.lo[k_day:k_day_end] < L - smin)[0]
    if not len(hits):
        return None
    k0 = k_day + int(hits[0])
    sigs = []
    attempt = 1
    end_k = k0
    weekend_skips = 0
    while attempt <= cfg.entry.max_attempts and k0 < len(b.t):
        ev, r, li = find_reclaim(b, L, k0, variant, cfg, horizon)
        if ev != "reclaim":
            end_k = r if r >= 0 else k0 + horizon
            break
        swept = float(b.lo[k0: r + 1].min())
        low_t = pd.Timestamp(b.t[li], tz="UTC")
        end_k = r
        if cfg.sweep.skip_weekend and cal.is_weekend(low_t) and weekend_skips < 3:
            # weekend low: not a trigger. Look for a fresh weekday sweep within the reclaim window.
            weekend_skips += 1
            nxt_end = min(len(b.t), r + 1 + cfg.reclaim.window_hours * 4)
            smin2 = sw.min_atr4h * np.nan_to_num(b.atr4[r + 1:nxt_end], nan=np.inf)
            h2 = np.nonzero(b.lo[r + 1:nxt_end] < L - smin2)[0]
            if not len(h2):
                sigs.append(_skipped(symbol, b, Lr, z, variant, entry_v, attempt, li, r, swept, "weekend_low"))
                break
            k0 = r + 1 + int(h2[0])
            continue
        if entry_v == "E1":
            ke = r
        else:
            ke = e2_entry(b, L, r, swept, cfg.entry.e2_expire_hours * 4)
            if ke < 0:
                break
        swept = float(b.lo[k0: ke + 1].min())
        entry = float(b.c[ke])
        stop = _stop(b, ke, swept, cfg)
        sigs.append(_signal(symbol, b, Lr, z, variant, entry_v, attempt, k0, li, r, ke, entry, stop, swept))
        end_k = ke
        # attempt 2: a new low below this stop within 7 days, while not accepted, then a fresh reclaim
        look_end = min(len(b.t), ke + 1 + 7 * 96)
        brk = np.nonzero(b.lo[ke + 1: look_end] < stop)[0]
        if not len(brk):
            break
        attempt += 1
        k0 = ke + 1 + int(brk[0])
        end_k = k0
    return end_k, sigs


def _base(symbol, b, Lr, z, variant, entry_v, attempt):
    return {"symbol": symbol, "side": "long" if b.sign > 0 else "short", "level": Lr,
            "level_tf": z["tf"], "pivot_tf": z.get("pivot_tf", ""), "level_kinds": z["kinds"],
            "level_type": level_type(z["kinds"], z.get("pivot_tf", "")), "zone_members": int(z["members"]),
            "level_valid_from": z["valid_from"], "level_pivot_time": z["pivot_time"],
            "reclaim_variant": variant, "entry_variant": entry_v, "attempt": attempt}


def _skipped(symbol, b, Lr, z, variant, entry_v, attempt, li, r, swept, why):
    d = _base(symbol, b, Lr, z, variant, entry_v, attempt)
    d.update({"skipped": why, "swept_low": abs(swept), "swept_time": pd.Timestamp(b.t[li], tz="UTC"),
              "reclaim_time": pd.Timestamp(b.t[r] + NS_15M, tz="UTC"), "entry_idx": -1})
    return d


def _signal(symbol, b, Lr, z, variant, entry_v, attempt, k0, li, r, ke, entry, stop, swept):
    d = _base(symbol, b, Lr, z, variant, entry_v, attempt)
    sgn = b.sign
    e_abs, s_abs = abs(entry), abs(stop)
    d.update({
        "skipped": "",
        "sweep_start": pd.Timestamp(b.t[k0], tz="UTC"),
        "swept_low": abs(swept), "swept_time": pd.Timestamp(b.t[li], tz="UTC"),
        "sweep_depth_pct": abs(swept - sgn * Lr) / Lr,
        "sweep_depth_atr4h": abs(swept - sgn * Lr) / b.atr4[k0] if b.atr4[k0] > 0 else np.nan,
        "reclaim_time": pd.Timestamp(b.t[r] + NS_15M, tz="UTC"),
        "entry_time": pd.Timestamp(b.t[ke] + NS_15M, tz="UTC"), "entry_idx": int(ke),
        "entry": e_abs, "stop": s_abs, "stop_pct": abs(e_abs - s_abs) / e_abs,
        "atr4h": float(b.atr4[ke]), "atr1d": float(b.atr1d[ke]),
    })
    return d


def _context(s: dict, D: DailyArrays, ls, sign, lo60, hi60, cfg) -> dict:
    """Targets, location, drawdown and calendar flags, known as of the signal (prior daily bars only)."""
    if s.get("skipped"):
        return {}
    e, stp = s["entry"], s["stop"]
    R = abs(e - stp)
    t_entry = s["entry_time"]
    act = ls.active(t_entry.value)
    if sign > 0:
        opp = ls.price[act & (ls.price >= e + cfg.targets.tp1_min_r * R)]
        tp1 = float(opp.min()) if len(opp) else np.nan
    else:
        opp = ls.price[act & (ls.price <= e - cfg.targets.tp1_min_r * R)]
        tp1 = float(opp.max()) if len(opp) else np.nan
    k = D.before(t_entry.value)
    n60, n120 = cfg.targets.range_lookback_days, cfg.targets.deep_dd_prior_high_days
    hi60r, lo60r = D.h[max(0, k - n60):k].max(), D.l[max(0, k - n60):k].min()
    hi120, lo120 = D.h[max(0, k - n120):k].max(), D.l[max(0, k - n120):k].min()
    if sign > 0:
        dd = 1 - s["swept_low"] / hi120
        tp2 = float(hi120) if dd >= cfg.filters.dd_crypto[0] else float(hi60r)
    else:
        dd = s["swept_low"] / lo120 - 1  # rally above the 120-day low (mirror)
        tp2 = float(lo120) if dd >= cfg.filters.dd_crypto[0] else float(lo60r)
    rr2 = (tp2 - e) / R * sign if R > 0 else np.nan
    if not np.isfinite(tp1) or (sign > 0 and tp1 >= tp2) or (sign < 0 and tp1 <= tp2):
        tp1_eff = e + sign * R  # fallback 1R
    else:
        tp1_eff = tp1
    L = s["level"]
    rng = hi60 - lo60
    if sign > 0:
        loc_ok = (L <= lo60 + cfg.levels.location_pct * rng) or (abs(L / lo60 - 1) <= cfg.levels.merge_pct)
    else:
        loc_ok = (L >= hi60 - cfg.levels.location_pct * rng) or (abs(L / hi60 - 1) <= cfg.levels.merge_pct)
    n_t, last_t = D.touches(L, s["level_valid_from"].value - 400 * NS_D, (t_entry.value // NS_D) * NS_D,
                            cfg.levels.merge_pct)
    return {
        "tp1": tp1, "tp1_eff": tp1_eff, "tp2": tp2, "rr_tp2": rr2,
        "dd_from_120d": dd, "range60_lo": lo60, "range60_hi": hi60,
        "f_location": bool(loc_ok),
        "f_stop_ok": s["stop_pct"] <= cfg.stop.max_stop_pct,
        "f_rr_ok": bool(rr2 >= cfg.targets.min_rr),
        "days_to_fomc": cal.days_to_fomc(t_entry),
        "days_to_qclose": cal.days_to_quarter_close(s["swept_time"]),
        "swept_weekend": cal.is_weekend(s["swept_time"]),
        "touches": n_t, "last_touch": last_t,
    }
