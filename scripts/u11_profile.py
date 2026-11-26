"""Backtest the scanner's CURRENT profile (config.yaml -> scanner) on a signal tag.

  python scripts/u06_signals.py v2      # regenerate with the current sweep / weekend settings
  python scripts/u11_profile.py v2      # -> reports/profile_v2.md
Uses scanner.reclaim / scanner.entry / scanner.required_filters (list, or {long: [...], short: [...]}) / scanner.shorts / scanner.tiers.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.analysis import brackets, enrich, load_signals, trades  # noqa: E402
from biss.metrics import stats, to_md  # noqa: E402
from biss.portfolio import shuffles  # noqa: E402

cfg = config.load()
REP = config.ROOT / "reports"


def row(t):
    s = stats(t) if len(t) else {"trades": 0}
    r = {k: s.get(k, np.nan) for k in ("trades", "win%", "avgR", "medR", "PF", "maxLossStreak", "maxDD_R",
                                        "medHold_d", "avg_stop%")}
    for sl in ("IS", "OOS", "HO"):
        x = t[t["slice"] == sl] if len(t) else t
        r[f"{sl}_n"], r[f"{sl}_avgR"] = len(x), (round(float(x.R.mean()), 3) if len(x) else np.nan)
    return r


def main(tag: str) -> None:
    sc = cfg.scanner
    df = enrich(load_signals(tag), cfg)
    df["F3_fomc"] = df["days_to_fomc"].abs() > cfg.filters.fomc_days
    rf = sc.required_filters
    flt = {s: list(rf[s]) if isinstance(rf, dict) else list(rf) for s in ("long", "short")}
    sel = list(sc.get("tiers") or [])
    tiers_all = ["T1", "T2", "T3", "T4", "T4pool"]
    sides = ["long", "short"] if sc.shorts else ["long"]
    rows = {}
    for side in sides:
        for lab, tiers in (("T1", ["T1"]), ("T2", ["T2"]), ("T3", ["T3"]), ("TradeFi", ["T4", "T4pool"]),
                           ("ALL", tiers_all)):
            rows[f"{side} {lab}"] = row(trades(df, reclaim=sc.reclaim, entry=sc.entry, side=side, tiers=tiers,
                                               filters=flt[side]))
    tab = pd.DataFrame(rows).T
    t_all = pd.concat([trades(df, reclaim=sc.reclaim, entry=sc.entry, side=s, tiers=sel or tiers_all, filters=flt[s])
                       for s in sides])
    pd_rows = {}
    for rp in cfg.sizing.risk_pct:
        s = shuffles(t_all, rp, cfg, brackets(), 100, cfg.validation.seed)
        pd_rows[f"{'+'.join(sel) or 'all'} signals @ {int(rp * 100)}%"] = {k: round(v, 2) for k, v in s.items()}
    md = [f"# Scanner profile backtest ({tag})\n",
          f"Reclaim {sc.reclaim}/{sc.entry}; required filters {flt}; FOMC +-{cfg.filters.fomc_days}d; sweep min "
          f"{cfg.sweep.min_atr4h} x ATR4h; weekend skip {cfg.sweep.skip_weekend}; sides {sides}; account tiers {sel or 'all'}; "
          f"open-risk cap {cfg.sizing.max_open_risk}; cluster cap {cfg.sizing.get('max_per_cluster')}.\n",
          to_md(tab), "\n## $1,000 account, mode (a), 100 random within-week orderings\n", to_md(pd.DataFrame(pd_rows).T)]
    (REP / f"profile_{tag}.md").write_text("\n".join(md), encoding="utf-8")
    print(tab[["trades", "win%", "avgR", "IS_avgR", "OOS_avgR", "HO_avgR"]].to_string())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "v2")
