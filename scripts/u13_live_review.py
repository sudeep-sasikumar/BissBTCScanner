"""Review the scanner's research database (docs/DATA.md). Read-only; proposes nothing by itself.

  python scripts/u13_live_review.py path/to/biss_YYYYMMDD.sqlite   -> reports/live_review.md

Sections: data coverage; passing vs failing setups (R net of estimated costs); the counterfactual of each filter;
exits compared; context at entry (funding, OI change, long/short, liquidations near the level, spread) split by outcome.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.metrics import to_md  # noqa: E402

cfg = config.load()
FEE_T, FEE_M = 0.0008, 0.0002
SLIP = dict(cfg.costs.slippage)
EXITS = ["r_partial_be", "r_fixed_2r", "r_fixed_3r", "r_tp1", "r_tp2"]


def net(df: pd.DataFrame, col: str) -> pd.Series:
    """Gross R minus estimated round-trip costs in R (taker in; taker out on losses, maker on wins)."""
    slip = df["tier"].map(SLIP).fillna(SLIP.get("T2", 0.001))
    out_fee = np.where(df[col] > 0, FEE_M, FEE_T + slip)
    cost = (FEE_T + slip + out_fee) / df["stop_pct"]
    return df[col] - cost


def md_table(df: pd.DataFrame) -> str:
    return to_md(df) if len(df) else "_none yet_"


def summarise(g: pd.DataFrame) -> pd.Series:
    r = g["net_plan"]
    return pd.Series({"n": len(g), "done": int(g["done"].fillna(0).sum()), "win%": round(100 * (r > 0).mean(), 1),
                      "avgR_net": round(r.mean(), 3), "medR_net": round(r.median(), 3),
                      "PF": round(r[r > 0].sum() / -r[r < 0].sum(), 2) if (r < 0).any() else np.inf,
                      "avg_MFE": round(g["mfe_r"].mean(), 2), "avg_MAE": round(g["mae_r"].mean(), 2)})


def main(path: str) -> None:
    conn = sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)
    q = lambda sql: pd.read_sql_query(sql, conn)  # noqa: E731
    out = [f"# Live research review ({Path(path).name})\n"]
    cov = q("SELECT MIN(ts) a, MAX(ts) b, COUNT(*) n FROM scans").iloc[0]
    out.append(f"Scans {int(cov.n)} from {pd.to_datetime(cov.a, unit='ms')} to {pd.to_datetime(cov.b, unit='ms')} UTC.\n")
    s = q("""SELECT s.*, t.done, t.r_partial_be, t.r_fixed_2r, t.r_fixed_3r, t.r_tp1, t.r_tp2, t.mfe_r, t.mae_r, t.state
             FROM setups s JOIN setup_tracks t ON t.key = s.key WHERE s.skipped = ''""")
    if s.empty:
        out.append("No tracked setups yet.")
    else:
        for c in EXITS:
            s[f"net_{c[2:]}"] = net(s, c)
        s["net_plan"] = s["net_partial_be"]
        s["group"] = np.where(s.passes == 1, "passes", "fails filters")
        out += ["## Passing vs failing (net R, the live plan)\n",
                md_table(s.groupby(["group", "side"]).apply(summarise, include_groups=False)), "",
                "## Live (entry after the scanner started) vs backfilled\n",
                md_table(s.groupby(["live", "group"]).apply(summarise, include_groups=False)), "",
                "## Setups that failed exactly one filter (what the filter keeps out)\n",
                md_table(s[(s.passes == 0) & ~s.failed.str.contains(",")].groupby("failed")
                         .apply(summarise, include_groups=False)), "",
                "## Exits compared, passing setups (net R)\n",
                md_table(s[s.passes == 1][[f"net_{c[2:]}" for c in EXITS]].describe().T.round(3)), ""]
        # context at entry: nearest hourly derivatives row before entry, liquidations within 1% of the level
        d = q("SELECT * FROM deriv_snap")
        liq = q("SELECT * FROM liquidations")
        rows = []
        for _, r in s.iterrows():
            x = {"key": r.key}
            dd = d[(d.symbol == r.symbol) & (d.ts <= r.entry_time)].sort_values("ts")
            if len(dd):
                last = dd.iloc[-1]
                prev = dd[dd.ts <= r.entry_time - 24 * 3_600_000]
                x.update({"ls_global": last.ls_global, "taker": last.taker_buy_sell, "bn_funding": last.bn_funding,
                          "oi_chg_24h": (last.bn_oi / prev.iloc[-1].bn_oi - 1) if len(prev) and prev.iloc[-1].bn_oi else None})
            lq = liq[(liq.symbol == r.symbol) & (liq.ts.between(r.swept_time - 3_600_000, r.reclaim_time or r.entry_time))]
            if r.level and len(lq):
                near = lq[(lq.price / r.level - 1).abs() <= 0.01]
                want = "long_liq" if r.side == "long" else "short_liq"
                x["liq_usd_at_level"] = near[near.side == want].usd.sum()
            rows.append(x)
        ctx = s.merge(pd.DataFrame(rows), on="key", how="left")
        ctx["outcome"] = np.where(ctx.net_plan > 0, "win", "loss")
        cols = [c for c in ("ls_global", "taker", "bn_funding", "oi_chg_24h", "liq_usd_at_level", "stop_pct",
                            "rr_tp2") if c in ctx]
        out += ["## Context at entry, medians by outcome (all tracked setups)\n",
                md_table(ctx.groupby(["side", "outcome"])[cols].median().round(4)), ""]
        feats = pd.json_normalize(s.features.map(json.loads))
        if "sweep_depth_atr4h" in feats:
            s["sweep_atr_bin"] = pd.qcut(feats["sweep_depth_atr4h"].astype(float), 4, duplicates="drop")
            out += ["## Sweep depth (ATR4h) quartiles\n",
                    md_table(s.groupby("sweep_atr_bin", observed=True).apply(summarise, include_groups=False)), ""]
    b = q("SELECT symbol, AVG(spread_bps) spread_bps, AVG(bid_usd_1 + ask_usd_1) depth_1pct_usd FROM book_snap "
          "GROUP BY symbol ORDER BY depth_1pct_usd")
    out += ["## WEEX order books (averages)\n", md_table(b.round(1).head(20)), ""]
    u = q("SELECT symbol, COUNT(*) days, AVG(rank) avg_rank FROM universe_snap WHERE scanned = 0 AND rank <= 50 "
          "GROUP BY symbol ORDER BY days DESC")
    out += ["## Coins in the top 50 that the scanner did not scan (list fixed at container start)\n",
            md_table(u.head(20)), ""]
    errs = q("SELECT kind, COUNT(*) n FROM events GROUP BY kind")
    out += ["## Events\n", md_table(errs)]
    rep = config.ROOT / "reports" / "live_review.md"
    rep.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out)[:4000])
    print(f"\n-> {rep}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(config.ROOT / "data" / "biss.sqlite"))
