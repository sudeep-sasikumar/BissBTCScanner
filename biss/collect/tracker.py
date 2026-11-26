"""Forward path of one setup on 15m bars, advanced incrementally (each scan feeds only the new bars).

Everything is in R (1R = |entry - stop|), gross of fees, direction-adjusted (shorts mirrored). Within a bar the
stop is assumed first, as in the backtest. Records:
  - MFE / MAE overall and at 1, 3, 7, 14, 30 days, and the R at each horizon's close;
  - first bar that touched -1R, +0.5R, +1R, +2R, +3R, TP1, TP2, and the first 15m close back through the level;
  - bars where -1R and +1R were both inside one bar before either was hit (order unknown on 15m);
  - outcome under several exits: partial_1r_be (the live plan), fixed 2R, fixed 3R, all at TP1, all at TP2.
A setup is done 30 days after entry; exits still open then are marked to the last close.
"""
from __future__ import annotations

DAY_MS = 86_400_000
HORIZONS = {"1d": 1, "3d": 3, "7d": 7, "14d": 14, "30d": 30}
TRACK_DAYS = 30
LEVELS = {"-1R": -1.0, "+0.5R": 0.5, "+1R": 1.0, "+2R": 2.0, "+3R": 3.0}


def new_state(entry: float, stop: float, tp1: float | None, tp2: float | None, level: float, side: str,
              entry_time_ms: int) -> dict:
    sign = 1 if side == "long" else -1
    R = abs(entry - stop)

    def r_of(p):
        return None if p is None or R <= 0 else sign * (p - entry) / R
    return {"sign": sign, "entry": entry, "R": R, "level_r": r_of(level), "tp1_r": r_of(tp1), "tp2_r": r_of(tp2),
            "t0": entry_time_ms, "last_bar": entry_time_ms - 15 * 60_000, "bars": 0, "mfe": 0.0, "mae": 0.0,
            "last_close_r": 0.0, "hz": {}, "hits": {}, "ambiguous": 0, "done": False,
            "exits": {"partial_1r_be": {"open": True, "half": False, "stop": -1.0, "realised": 0.0, "left": 1.0},
                      "fixed_2r": {"open": True, "target": 2.0}, "fixed_3r": {"open": True, "target": 3.0},
                      "tp1": {"open": True, "target": tp1 is not None and r_of(tp1)},
                      "tp2": {"open": True, "target": tp2 is not None and r_of(tp2)}}}


def _close_simple(x: dict, r: float, t: int) -> None:
    x.update({"open": False, "r": r, "exit_t": t})


def advance(st: dict, bars) -> dict:
    """bars: iterable of (open_time_ms, open, high, low, close), ascending. Only bars after st['last_bar'] count."""
    if st["done"] or st["R"] <= 0:
        st["done"] = True
        return st
    sgn, e, R = st["sign"], st["entry"], st["R"]
    end = st["t0"] + TRACK_DAYS * DAY_MS
    for t, o, h, lo, c in bars:
        t = int(t)
        if t <= st["last_bar"] or t < st["t0"]:
            continue
        if t >= end:
            st["done"] = True
            break
        hi_r = sgn * ((h if sgn > 0 else lo) - e) / R
        lo_r = sgn * ((lo if sgn > 0 else h) - e) / R
        c_r = sgn * (c - e) / R
        st["bars"] += 1
        st["last_bar"] = t
        st["last_close_r"] = c_r
        st["mfe"] = max(st["mfe"], hi_r)
        st["mae"] = min(st["mae"], lo_r)
        age_days = (t + 15 * 60_000 - st["t0"]) / DAY_MS
        for k, d in HORIZONS.items():
            if age_days <= d:
                st["hz"][k] = {"mfe": st["mfe"], "mae": st["mae"], "close_r": c_r}
        hits = st["hits"]
        if "-1R" not in hits and "+1R" not in hits and lo_r <= -1 and hi_r >= 1:
            st["ambiguous"] += 1
        for name, lv in LEVELS.items():
            if name not in hits and ((lv < 0 and lo_r <= lv) or (lv > 0 and hi_r >= lv)):
                hits[name] = t
        for name in ("tp1", "tp2"):
            tr = st[f"{name}_r"]
            if tr is not None and name not in hits and hi_r >= tr:
                hits[name] = t
        lv_r = st["level_r"]
        if lv_r is not None and "close_back" not in hits and c_r < lv_r:
            hits["close_back"] = t
        ex = st["exits"]
        p = ex["partial_1r_be"]
        if p["open"]:                                   # same order as the live paper tracker: stop, +1R, TP2
            if lo_r <= p["stop"]:
                p["realised"] += p["left"] * p["stop"]
                p["left"] = 0.0
                _close_simple(p, p["realised"], t)
            else:
                if not p["half"] and hi_r >= 1.0:
                    p["realised"] += 0.5
                    p["left"] = 0.5
                    p["half"] = True
                    p["stop"] = 0.0
                tp2 = st["tp2_r"]
                if tp2 is not None and hi_r >= tp2:
                    p["realised"] += p["left"] * tp2
                    p["left"] = 0.0
                    _close_simple(p, p["realised"], t)
        for name in ("fixed_2r", "fixed_3r", "tp1", "tp2"):
            x = ex[name]
            if not x["open"]:
                continue
            if lo_r <= -1.0:
                _close_simple(x, -1.0, t)
            elif x["target"] and hi_r >= x["target"]:
                _close_simple(x, float(x["target"]), t)
    if st["done"]:
        for name, x in st["exits"].items():
            if x["open"]:
                r = (x["realised"] + x["left"] * st["last_close_r"]) if name == "partial_1r_be" else st["last_close_r"]
                x.update({"open": False, "r": r, "exit_t": st["last_bar"], "marked": True})
    return st


def summary(st: dict) -> dict:
    ex = st["exits"]

    def r(name):
        x = ex[name]
        if not x["open"]:
            return x.get("r")
        if name == "partial_1r_be":                         # open: realised + unrealised at the last close
            return x["realised"] + x["left"] * st["last_close_r"]
        return st["last_close_r"]
    return {"r_partial_be": r("partial_1r_be"), "r_fixed_2r": r("fixed_2r"), "r_fixed_3r": r("fixed_3r"),
            "r_tp1": r("tp1"), "r_tp2": r("tp2"), "mfe_r": st["mfe"], "mae_r": st["mae"]}
