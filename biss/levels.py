"""HTF levels (section 5.1): validated weekly/monthly swing pivots, yearly/monthly/weekly opens, prior range
extremes. Every level carries `valid_from`, the first moment it may be used (no lookahead)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import resample

PRIORITY = {"M": 0, "W": 1, "D": 2}
KIND_RANK = {"pivot_low": 0, "pivot_high": 0, "range_low": 1, "range_high": 1, "open_year": 2,
             "open_month": 3, "open_week": 4}


def _next_open(idx: pd.DatetimeIndex, k: int, tf: str) -> pd.Timestamp:
    if k + 1 < len(idx):
        return idx[k + 1]
    return idx[k] + {"M": pd.offsets.MonthBegin(1), "W": pd.Timedelta(days=7), "D": pd.Timedelta(days=1)}[tf]


def pivots(bars: pd.DataFrame, tf: str, p: int, min_move: float, k: float, n_valid: int,
           med_lookback: int) -> list[dict]:
    """Confirmed pivots (p bars each side) validated by a move >= max(min_move, k * median range) within
    n_valid bars. Usable from the bar after both confirmation and the validating move."""
    h, l, c = bars["high"].to_numpy(), bars["low"].to_numpy(), bars["close"].to_numpy()
    idx = bars.index
    rng = (h - l) / c
    out = []
    n = len(bars)
    for i in range(p, n - p):
        medr = float(np.nanmedian(rng[max(0, i - med_lookback): i + 1]))
        thr = max(min_move, k * medr)
        seg_hi = h[i + 1: i + 1 + n_valid]
        seg_lo = l[i + 1: i + 1 + n_valid]
        if l[i] < l[i - p: i].min() and l[i] <= l[i + 1: i + p + 1].min():
            hit = np.nonzero(seg_hi >= l[i] * (1 + thr))[0]
            if len(hit):
                j = i + 1 + int(hit[0])
                out.append({"price": float(l[i]), "tf": tf, "kind": "pivot_low", "pivot_time": idx[i],
                            "valid_from": _next_open(idx, max(j, i + p), tf), "valid_to": pd.NaT,
                            "move": float(thr)})
        if h[i] > h[i - p: i].max() and h[i] >= h[i + 1: i + p + 1].max():
            hit = np.nonzero(seg_lo <= h[i] * (1 - thr))[0]
            if len(hit):
                j = i + 1 + int(hit[0])
                out.append({"price": float(h[i]), "tf": tf, "kind": "pivot_high", "pivot_time": idx[i],
                            "valid_from": _next_open(idx, max(j, i + p), tf), "valid_to": pd.NaT,
                            "move": float(thr)})
    return out


def period_levels(daily: pd.DataFrame, opens: list[str], prior_range: bool) -> list[dict]:
    out = []
    for tf, rule, kind in (("Y", "Y", "open_year"), ("M", "M", "open_month"), ("W", "W", "open_week")):
        bars = resample(daily, rule)
        idx = bars.index
        nxt = list(idx[1:]) + [idx[-1] + (pd.DateOffset(years=1) if tf == "Y" else
                                         pd.offsets.MonthBegin(1) if tf == "M" else pd.Timedelta(days=7))]
        name = {"Y": "yearly", "M": "monthly", "W": "weekly"}[tf]
        if name in opens:
            for t, t2, o in zip(idx, nxt, bars["open"].to_numpy()):
                out.append({"price": float(o), "tf": "M" if tf == "Y" else tf, "kind": kind, "pivot_time": t,
                            "valid_from": t, "valid_to": t2, "move": np.nan})
        if prior_range and tf in ("M", "W"):
            for i in range(len(idx) - 1):
                t_from, t_to = nxt[i], nxt[i + 1] if i + 1 < len(nxt) else nxt[i] + (nxt[i] - idx[i])
                out.append({"price": float(bars["high"].iloc[i]), "tf": tf, "kind": "range_high",
                            "pivot_time": idx[i], "valid_from": t_from, "valid_to": t_to, "move": np.nan})
                out.append({"price": float(bars["low"].iloc[i]), "tf": tf, "kind": "range_low",
                            "pivot_time": idx[i], "valid_from": t_from, "valid_to": t_to, "move": np.nan})
    return out


def build_levels(daily: pd.DataFrame, cfg) -> pd.DataFrame:
    """All candidate levels for one symbol from its daily bars."""
    lv = cfg.levels
    rows: list[dict] = []
    for tf, rule in (("M", "M"), ("W", "W")):
        bars = resample(daily, rule)
        if len(bars) < 2 * lv.pivot_bars + 2:
            continue
        rows += pivots(bars, tf, lv.pivot_bars, lv.min_move_pct, lv.k_median_range, lv.validate_within,
                       lv.median_range_lookback)
    dp = lv.get("daily_pivots")
    if dp:  # rule C baseline only
        rows += pivots(daily, "D", dp["pivot_bars"], dp["min_move_pct"], dp["k_median_range"], dp["validate_within"],
                       lv.median_range_lookback)
    if not lv.get("pivots_only"):
        rows += period_levels(daily, list(lv.include_opens), lv.include_prior_range)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["prio"] = df["tf"].map(PRIORITY) * 10 + df["kind"].map(KIND_RANK)
    return df.sort_values("valid_from").reset_index(drop=True)


def active(levels: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    if levels.empty:
        return levels
    m = (levels["valid_from"] <= t) & (levels["valid_to"].isna() | (levels["valid_to"] > t))
    return levels[m]


def merge_zones(lv: pd.DataFrame, merge_pct: float) -> pd.DataFrame:
    """Merge levels within merge_pct (chained) into zones. Zone price = its highest-priority member
    (monthly pivot > weekly pivot > range > opens; newest wins ties). Members are counted."""
    if lv.empty:
        return lv
    lv = lv.sort_values("price")
    p = lv["price"].to_numpy()
    zid = np.r_[0, np.cumsum(p[1:] > p[:-1] * (1 + merge_pct))]
    lv = lv.assign(zid=zid, _vf=lv["valid_from"].astype("int64"))
    best = lv.sort_values(["zid", "prio", "_vf"], ascending=[True, True, False]).drop_duplicates("zid")
    g = lv.groupby("zid")
    best = best.set_index("zid")
    best["members"] = g.size()
    best["zone_lo"] = g["price"].min()
    best["zone_hi"] = g["price"].max()
    best["kinds"] = g["kind"].agg(lambda k: ",".join(sorted(set(k))))
    piv = lv[lv["kind"].str.startswith("pivot")]
    ptf = piv.groupby("zid")["tf"].agg(lambda t: "M" if "M" in set(t) else "W" if "W" in set(t) else "D")
    best["pivot_tf"] = ptf.reindex(best.index).fillna("")
    best["tf"] = g["tf"].agg(lambda t: "M" if "M" in set(t) else "W" if "W" in set(t) else "D")
    return best.drop(columns=["_vf"]).reset_index(drop=True)


def touches(daily: pd.DataFrame, price: float, since: pd.Timestamp, until: pd.Timestamp, tol: float) -> tuple[int, pd.Timestamp | None]:
    """Distinct touch episodes (daily range within tol of price, separated by >= 3 days) and last touch day."""
    d = daily[(daily.index >= since) & (daily.index < until)]
    hit = d[(d["low"] <= price * (1 + tol)) & (d["high"] >= price * (1 - tol))]
    if hit.empty:
        return 0, None
    gaps = hit.index.to_series().diff() > pd.Timedelta(days=3)
    return int(gaps.sum()) + 1, hit.index[-1]


def level_type(kinds: str, pivot_tf: str) -> str:
    """Reporting bucket: monthly / weekly (pivots) / range / open."""
    if pivot_tf:
        return {"M": "monthly", "W": "weekly", "D": "daily"}[pivot_tf]
    if "range" in kinds:
        return "range"
    return "open"


class LevelSet:
    """Numpy view of a symbol's levels for fast as-of queries."""

    def __init__(self, df: pd.DataFrame):
        self.n = len(df)
        if not self.n:
            return
        self.price = df["price"].to_numpy(float)
        self.vf = pd.to_datetime(df["valid_from"], utc=True).dt.as_unit("ns").astype("int64").to_numpy()
        vt = pd.to_datetime(df["valid_to"], utc=True)
        big = np.iinfo(np.int64).max
        self.vt = np.array([big if pd.isna(x) else x.value for x in vt.dt.as_unit("ns")], dtype=np.int64)
        self.prio = df["prio"].to_numpy(int)
        self.tf = df["tf"].to_numpy(str)
        self.kind = df["kind"].to_numpy(str)
        self.pt = pd.to_datetime(df["pivot_time"], utc=True)

    def active(self, t_ns: int) -> np.ndarray:
        return (self.vf <= t_ns) & (self.vt > t_ns)

    def zone_of(self, p: float, mask: np.ndarray, merge_pct: float) -> dict:
        """Zone (chained merge within merge_pct) among `mask` levels that contains price p (p must be one of
        the masked prices)."""
        idx = np.nonzero(mask)[0]
        pr = self.price[idx]
        o = np.argsort(pr, kind="stable")
        idx, pr = idx[o], pr[o]
        zid = np.r_[0, np.cumsum(pr[1:] > pr[:-1] * (1 + merge_pct))]
        pos = int(np.argmin(np.abs(pr - p)))
        mem = idx[zid == zid[pos]]
        best = mem[np.lexsort((-self.vf[mem], self.prio[mem]))[0]]
        piv_tfs = {self.tf[i] for i in mem if self.kind[i].startswith("pivot")}
        ptf = ("M" if "M" in piv_tfs else "W" if "W" in piv_tfs else "D") if piv_tfs else ""
        tfs = {self.tf[i] for i in mem}
        return {"price": float(self.price[best]), "tf": "M" if "M" in tfs else "W" if "W" in tfs else "D",
                "pivot_tf": ptf, "kinds": ",".join(sorted({self.kind[i] for i in mem})), "members": len(mem),
                "zone_lo": float(self.price[mem].min()), "zone_hi": float(self.price[mem].max()),
                "valid_from": pd.Timestamp(int(self.vf[best]), tz="UTC"), "pivot_time": self.pt.iloc[best]}
