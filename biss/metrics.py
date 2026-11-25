"""Per-variant statistics (section 9B)."""
from __future__ import annotations

import numpy as np
import pandas as pd

WIN, LOSS = 0.1, -0.1


def streak(r: np.ndarray) -> int:
    best = cur = 0
    for x in r:
        cur = cur + 1 if x < LOSS else 0
        best = max(best, cur)
    return best


def r_drawdown(r: np.ndarray) -> float:
    """Max drawdown of cumulative R (in R)."""
    if not len(r):
        return 0.0
    c = np.cumsum(r)
    return float((np.maximum.accumulate(np.r_[0, c])[1:] - c).max())


def stats(t: pd.DataFrame, rcol: str = "R") -> dict:
    if t.empty:
        return {"trades": 0}
    t = t.sort_values("entry_time")
    r = t[rcol].to_numpy(float)
    pos, neg = r[r > 0].sum(), -r[r < 0].sum()
    top10 = np.sort(r)[::-1][:10].sum()
    span_days = (t["exit_time"].max() - t["entry_time"].min()).days or 1
    held = (t["exit_time"] - t["entry_time"]).dt.total_seconds().sum() / 86400
    out = {
        "trades": len(t),
        "win%": round(100 * (r > WIN).mean(), 1), "loss%": round(100 * (r < LOSS).mean(), 1),
        "scratch%": round(100 * ((r >= LOSS) & (r <= WIN)).mean(), 1),
        "avgR": round(r.mean(), 3), "medR": round(float(np.median(r)), 3),
        "PF": round(pos / neg, 2) if neg > 0 else np.inf,
        "sumR": round(r.sum(), 1), "maxLossStreak": streak(r), "maxDD_R": round(r_drawdown(r), 1),
        "medHold_d": round(float(t["hold_days"].median()), 1) if "hold_days" in t else np.nan,
        "exposure": round(held / span_days, 2),
        "avg_stop%": round(100 * t["stop_pct"].mean(), 2),
        "avgR_ex_top10": round((r.sum() - top10) / max(len(r) - 10, 1), 3),
        "top10_share%": round(100 * top10 / r.sum(), 0) if r.sum() > 0 else np.nan,
        "funding_R": round(float((t["funding_frac"] / t["stop_pct"]).sum()), 2) if "funding_frac" in t else np.nan,
        "fees_R_avg": round(float((t["fees_frac"] / t["stop_pct"]).mean()), 3) if "fees_frac" in t else np.nan,
    }
    if "lev_needed" in t:
        out["avg_lev_need"] = round(float(t["lev_needed"].mean()), 1)
        out["max_lev_need"] = round(float(t["lev_needed"].max()), 1)
        out["at_cap%"] = round(100 * t["at_cap"].mean(), 1)
    return out


def table(groups: dict[str, pd.DataFrame], rcol: str = "R") -> pd.DataFrame:
    return pd.DataFrame({k: stats(v, rcol) for k, v in groups.items()}).T


def to_md(df: pd.DataFrame, floatfmt: str = "g") -> str:
    df = df.copy()
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join([""] + cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for idx, row in df.iterrows():
        vals = []
        for v in row.to_numpy():
            if isinstance(v, float):
                vals.append("" if np.isnan(v) else f"{v:{floatfmt}}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join([str(idx)] + vals) + " |")
    return "\n".join(lines)
