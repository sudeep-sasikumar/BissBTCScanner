"""Exit simulation on 15m bars (section 5.6, 8.5), in direction space (see setups.Bars).

Rules:
- position opens at the entry bar's close; exits are evaluated from the next bar.
- a bar that touches both the stop and a target is resolved with 1m bars (resolver); without 1m data the
  stop is assumed first.
- a bar that OPENS beyond the stop fills at its open (gap), not at the stop.
- stop moves (breakeven, trail) apply from the bar after the trigger.
- targets are resting limits: maker fee, filled at the target price. Entries, stops and time/rule exits are
  market orders: taker fee + slippage.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

from .setups import NS_D, Bars

MGMT = ("partial_1r_be", "fixed_2r", "fixed_3r", "partial_tp1", "trail_4h_hl", "time_stop", "close_below_exit")


def targets_for(mgmt: str, entry: float, R: float, tp1: float, tp2: float) -> list[tuple[float, float, bool]]:
    """(price, fraction of ORIGINAL size, move stop to entry after fill) in direction space."""
    if mgmt in ("partial_1r_be", "time_stop", "close_below_exit"):
        return [(entry + R, 0.5, True), (tp2, 0.5, False)]
    if mgmt == "fixed_2r":
        return [(entry + 2 * R, 1.0, False)]
    if mgmt == "fixed_3r":
        return [(entry + 3 * R, 1.0, False)]
    if mgmt == "partial_tp1":
        return [(tp1, 0.5, True), (tp2, 0.5, False)]
    if mgmt == "trail_4h_hl":
        return [(tp2, 1.0, False)]
    raise ValueError(mgmt)


def _scan(arr: np.ndarray, v: float, k: int, le: bool) -> int:
    """first index >= k with arr <= v (le) or arr >= v; chunked so early hits stay cheap."""
    n = len(arr)
    step = 256
    while k < n:
        seg = arr[k: k + step]
        idx = np.flatnonzero(seg <= v if le else seg >= v)
        if len(idx):
            return k + int(idx[0])
        k += step
        step = min(step * 4, 1 << 16)
    return -1


def trail_updates(b: Bars, ke: int, entry: float, stop: float, pivot: int = 2, atr_mult: float = 0.25):
    """(15m index from which the new stop applies, new stop) for each confirmed 4h higher low after entry."""
    is4 = np.flatnonzero(b.is4h[ke + 1:]) + ke + 1
    if len(is4) < 2 * pivot + 1:
        return []
    starts = np.r_[ke + 1, is4[:-1] + 1]
    lows = np.minimum.reduceat(b.lo, starts)[: len(is4)] if starts[-1] < len(b.lo) else \
        np.array([b.lo[s_: e + 1].min() for s_, e in zip(starts, is4)])
    m = np.arange(pivot, len(lows) - pivot)
    if not len(m):
        return []
    left = np.min(np.stack([lows[m - i] for i in range(1, pivot + 1)]), axis=0)
    right = np.min(np.stack([lows[m + i] for i in range(1, pivot + 1)]), axis=0)
    piv = m[(lows[m] < left) & (lows[m] <= right)]
    out, last_pl, cur = [], -np.inf, stop
    for mm in piv:
        pl = lows[mm]
        if pl > last_pl:
            a4 = b.atr4[is4[mm]]
            new = pl - atr_mult * (a4 if np.isfinite(a4) else 0)
            if new > cur:
                out.append((int(is4[mm + pivot]) + 1, float(new)))
                cur = new
        last_pl = pl
    return out


def simulate(b: Bars, ke: int, entry: float, stop: float, tp1: float, tp2: float, level: float, mgmt: str,
             fee_taker: float, fee_maker: float, slip: float,
             resolver: Callable[[int, float, float], str] | None = None,
             funding_t: np.ndarray | None = None, funding_r: np.ndarray | None = None,
             time_stop_days: int = 20) -> dict:
    """All prices in direction space. Returns R after costs and exit details."""
    n = len(b.t)
    R = entry - stop
    absE = abs(entry)
    tg = sorted(targets_for(mgmt, entry, R, tp1, tp2))
    f = 1.0
    s = stop
    legs: list[tuple[int, float, float, str]] = []  # (bar, fraction, fill, why)
    fees = fee_taker + slip  # entry: taker fee + slippage (as a fraction of notional)
    k = ke + 1
    hit1 = False
    trails = trail_updates(b, ke, entry, stop) if mgmt == "trail_4h_hl" else []
    ti = 0
    tstop_k = ke + int(time_stop_days * NS_D // b.bar_ns) if mgmt == "time_stop" else -1
    cb = (np.flatnonzero(b.isday[ke + 1:] & (b.c[ke + 1:] < level)) + ke + 1) if mgmt == "close_below_exit" \
        else np.array([], int)
    ambiguous = 0
    while f > 1e-9 and k < n:
        js = _scan(b.lo, s, k, True)
        jt = _scan(b.h, tg[0][0], k, False) if tg else -1
        jtr = trails[ti][0] if ti < len(trails) else -1
        jx = -1
        if k <= tstop_k < n and not hit1:
            jx = tstop_k
        if len(cb):
            c2 = cb[cb >= k]
            if len(c2) and (jx < 0 or c2[0] < jx):
                jx = int(c2[0])
        ev = [(j, w) for j, w in ((js, "stop"), (jt, "tgt"), (jx, "rule"), (jtr, "trail")) if j >= 0]
        if not ev:
            break
        j = min(x for x, _ in ev)
        kinds = {w for x, w in ev if x == j}
        if "trail" in kinds and kinds == {"trail"}:
            s = max(s, trails[ti][1])
            ti += 1
            k = j
            continue
        if "trail" in kinds:  # trail applies from bar j: tighter stop may now be touched this bar
            s = max(s, trails[ti][1])
            ti += 1
            k = j
            continue
        order = []
        if "stop" in kinds and "tgt" in kinds:
            ambiguous += 1
            first = resolver(int(b.t[j]), s, tg[0][0]) if resolver else "stop"
            order = ["tgt", "stop"] if first == "tgt" else ["stop"]
        elif "stop" in kinds:
            order = ["stop"]
        elif "tgt" in kinds:
            order = ["tgt"]
        if "rule" in kinds and not order:
            fill = b.c[j] - slip * abs(b.c[j])
            legs.append((j, f, fill, "rule"))
            fees += f * fee_taker
            f = 0
            break
        moved = False
        for w in order:
            if w == "tgt":
                while tg and b.h[j] >= tg[0][0] and f > 1e-9:
                    px, frac, be = tg.pop(0)
                    q = min(frac, f)
                    legs.append((j, q, px, "tgt"))
                    fees += q * fee_maker
                    f -= q
                    hit1 = True
                    if be:
                        moved = True
            else:
                fill = min(b.o[j], s) if b.o[j] <= s else s
                fill -= slip * abs(fill)
                legs.append((j, f, fill, "stop"))
                fees += f * fee_taker
                f = 0
        if moved:
            s = max(s, entry)
        if "rule" in kinds and f > 1e-9:
            fill = b.c[j] - slip * abs(b.c[j])
            legs.append((j, f, fill, "rule"))
            fees += f * fee_taker
            f = 0
        k = j + 1
    open_ = f > 1e-9
    if open_:
        legs.append((n - 1, f, b.c[n - 1], "open"))
    gross = sum(q * (px - entry) for _, q, px, _ in legs) / absE
    # funding: long pays positive rates (direction space handles the sign via b.sign)
    fund = 0.0
    if funding_t is not None and len(funding_t):
        t0 = b.t[ke] + b.bar_ns
        rem = 1.0
        t_prev = t0
        for j, q, _, _ in sorted(legs):
            t_ex = b.t[j] + b.bar_ns
            m = (funding_t > t_prev) & (funding_t <= t_ex)
            fund += rem * float(funding_r[m].sum()) * b.sign
            rem -= q
            t_prev = t_ex
    pnl = gross - fees - fund
    stop_frac = R / absE
    last = max(legs)[0]
    mae = float(b.lo[ke + 1: last + 1].min()) if last > ke else entry
    why = [w for _, _, _, w in legs]
    if open_:
        outcome = "open"
    elif why[-1] == "stop":
        outcome = "stop" if len(why) == 1 else ("be" if abs(legs[-1][2] - entry) / absE < stop_frac * 0.2 else "stop_after_partial")
    elif why[-1] == "tgt":
        outcome = "target"
    else:
        outcome = "rule"
    if outcome == "stop" and s > stop:  # trailed stop
        outcome = "trail"
    return {"R": pnl / stop_frac, "gross_R": gross / stop_frac, "fees_frac": fees, "funding_frac": fund,
            "exit_idx": int(last), "exit_time_ns": int(b.t[last] + b.bar_ns),
            "exit_price": abs(legs[-1][2]), "outcome": outcome, "hold_days": (b.t[last] - b.t[ke]) / NS_D,
            "mae_frac": (entry - mae) / absE, "ambiguous_bars": ambiguous, "partial_hit": hit1}
