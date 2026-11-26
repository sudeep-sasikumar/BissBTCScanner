"""Final rule set after the section-8 protocol, its ablation, account sims, journal and reference cases.

Protocol result (reports/tables/filter_verdicts.csv): keep only filters whose removal lowers avg R in IS, OOS
and HO. Variant chosen on IS only (u07): R3w/E2. Writes reports/final.md, reports/journal.csv,
reports/tables/final_*.csv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.analysis import FILTERS, brackets, enrich, load_signals, trades  # noqa: E402
from biss.metrics import stats, to_md  # noqa: E402
from biss.portfolio import shuffles, simulate  # noqa: E402

cfg = config.load()
REP = config.ROOT / "reports"
TAB = REP / "tables"
REFS = [
    ("BTC weekly ~58.9k, swept 30 Jun 2026, reclaimed 1 Jul", "BTCUSDT", 58900, "2026-06-29", "2026-07-02"),
    ("HYPE ~52.64, swept 31 Jul 2026, reclaimed 3 Aug", "HYPEUSDT", 52.64, "2026-07-30", "2026-08-04"),
    ("ZEC ~300.8, swept 5 Jun 2026", "ZECUSDT", 300.8, "2026-06-03", "2026-06-08"),
    ("BTC below the lows, back above ~61.5k (17-20 Nov 2026)", "BTCUSDT", 61500, "2026-11-16", "2026-11-21"),
    ("BTC 57.3-57.7k higher-low plan (23 Nov 2026)", "BTCUSDT", 57500, "2026-11-23", "2026-11-26"),
]


def row(t):
    s = stats(t) if len(t) else {"trades": 0}
    keys = ["trades", "win%", "loss%", "scratch%", "avgR", "medR", "PF", "maxLossStreak", "maxDD_R", "medHold_d",
            "avg_stop%", "avg_lev_need", "at_cap%", "funding_R", "fees_R_avg", "avgR_ex_top10", "top10_share%"]
    r = {k: s.get(k, np.nan) for k in keys}
    for sl in ("IS", "OOS", "HO"):
        x = t[t["slice"] == sl] if len(t) else t
        r[f"{sl}_n"], r[f"{sl}_avgR"] = len(x), (round(float(x["R"].mean()), 3) if len(x) else np.nan)
    return r


def main() -> None:
    verd = pd.read_csv(TAB / "filter_verdicts.csv", index_col=0)["helps_in_all_3_slices"]
    keep = [f for f in FILTERS if bool(verd.get(f, False))]
    dropped = [f for f in FILTERS if f not in keep]
    raw = load_signals("main", keep_skipped_for={r[1] for r in REFS})
    refraw = raw[raw.symbol.isin({r[1] for r in REFS}) & (raw.side == "long")].copy()
    df = enrich(raw, cfg)
    del raw
    RV, EV = "R3w", "E2"
    md = ["# Final rule set (after the section 8 protocol)\n",
          f"Variant chosen on the in-sample slice only: **{RV}/{EV}** (weekly close back above the swept HTF level, "
          "then the first 15m pullback that holds the level). "
          f"Filters kept (removing each lowered avg R in IS, OOS and holdout): **{', '.join(keep)}**. "
          f"Dropped: {', '.join(dropped)}.\n"]
    rows = {}
    for lab, tiers, flt, mg in [
        ("FINAL T1+T2, 50%@1R+BE", ["T1", "T2"], keep, "partial_1r_be"),
        ("FINAL T1+T2, 50%@TP1+BE", ["T1", "T2"], keep, "partial_tp1"),
        ("FINAL T1 only", ["T1"], keep, "partial_1r_be"),
        ("FINAL T2 only", ["T2"], keep, "partial_1r_be"),
        ("FINAL T3", ["T3"], keep, "partial_1r_be"),
        ("FINAL T4 (5 liquid TradeFi)", ["T4"], keep, "partial_1r_be"),
        ("FINAL T4 pool (other TradeFi)", ["T4pool"], keep, "partial_1r_be"),
        ("same, all 7 filters (pre-protocol), T1+T2", ["T1", "T2"], FILTERS, "partial_1r_be"),
        ("15m R1/E1 with final filters, T1+T2", ["T1", "T2"], keep, "partial_1r_be"),
        ("4h R2/E1 with final filters, T1+T2", ["T1", "T2"], keep, "partial_1r_be"),
    ]:
        rv, ev = ("R1", "E1") if "15m" in lab else ("R2", "E1") if "4h R2" in lab else (RV, EV)
        rows[lab] = row(trades(df, mgmt=mg, reclaim=rv, entry=ev, tiers=tiers, filters=flt))
    b = pd.read_csv(REP / "baseline_refined_weex.csv", parse_dates=["entry_time", "exit_time"])
    b = b[(b["rank"] <= 50) & b["kept"]]
    from biss.tiers import base_of
    from biss.universe import is_holdout
    ho = b.symbol.map(lambda s: is_holdout(base_of(s), cfg.validation.holdout_frac, cfg.validation.seed))
    b["slice"] = np.where(ho, "HO", np.where(b.entry_time < pd.Timestamp(cfg.validation.split_date, tz="UTC"), "IS", "OOS"))
    rows["BASELINE refined weekly (WEEX costs, my reproduction)"] = row(b)
    tab = pd.DataFrame(rows).T
    tab.to_csv(TAB / "final_summary.csv")
    md += ["## Final vs baselines\n", "Documented refined result: 158 trades, 68% win, +0.97R. Rule C: about 0R "
           "(reproduced: -0.09 to -0.01R, reports/backtest.md section 2).\n", to_md(tab), "\n"]

    # ablation of the final set
    t_final = trades(df, reclaim=RV, entry=EV, tiers=["T1", "T2"], filters=keep)
    ab = {"final": row(t_final)}
    for f in keep:
        ab[f"without {f}"] = row(trades(df, reclaim=RV, entry=EV, tiers=["T1", "T2"], filters=[x for x in keep if x != f]))
    for f in dropped:
        ab[f"plus {f}"] = row(trades(df, reclaim=RV, entry=EV, tiers=["T1", "T2"], filters=keep + [f]))
    ab = pd.DataFrame(ab).T
    ab.to_csv(TAB / "final_ablation.csv")
    md += ["## Ablation of the final set (T1+T2)\n", to_md(ab), "\n"]

    # by level type and year
    md += ["## Final set by level type\n", to_md(pd.DataFrame({k: row(v) for k, v in t_final.groupby("level_type")}).T),
           "\n## Final set by year\n", to_md(pd.DataFrame({str(k): row(v) for k, v in t_final.groupby("year")}).T), "\n"]
    top = t_final.sort_values("R", ascending=False).head(10)[["symbol", "entry_time", "level", "level_type", "R"]]
    md += [f"Top-10 trades: {top.R.sum():.1f}R of {t_final.R.sum():.1f}R total; avg R without them "
           f"{(t_final.R.sum() - top.R.sum()) / max(len(t_final) - 10, 1):.2f}.\n\n", to_md(top.set_index("symbol")), "\n"]

    # account sims
    br = brackets()
    pdep = {}
    for tiers in (["T1"], ["T2"], ["T1", "T2"]):
        t = trades(df, reclaim=RV, entry=EV, tiers=tiers, filters=keep)
        for rp in cfg.sizing.risk_pct:
            s = shuffles(t, rp, cfg, br, cfg.validation.shuffles, cfg.validation.seed)
            pdep[f"{'+'.join(tiers)} @ {int(rp * 100)}%"] = {k: round(v, 2) for k, v in s.items()}
    for rp in (0.2, 0.35, 0.5):
        s = shuffles(t_final, rp, cfg, br, cfg.validation.shuffles, cfg.validation.seed, mode="b")
        pdep[f"mode (b) T1+T2 @ {int(rp * 100)}%"] = {k: round(v, 2) for k, v in s.items()}
    pdep = pd.DataFrame(pdep).T
    pdep.to_csv(TAB / "final_path_dependence.csv")
    md += ["## $1,000 account, 300 random within-week orderings (mode a unless stated)\n", to_md(pdep), "\n"]
    res = simulate(t_final, 0.03, cfg, br, keep_journal=True)
    jr = res["journal"]
    jr.to_csv(REP / "journal.csv", index=False)
    md.append(f"Journal (`reports/journal.csv`): 3% risk, chronological: {res['taken']} taken, skipped {res['skipped']}, "
              f"sized at a leverage cap {res['cap_hits']}, shrunk for margin {res['shrunk']}, avg leverage "
              f"{res['avg_lev']:.1f}x (max {res['max_lev']:.1f}x), $1,000 -> ${res['end']:,.0f}, max DD {100 * res['max_dd']:.0f}%. "
              f"Leverage needed for the 1x-stop liquidation buffer: median {t_final.lev_needed.median():.1f}x; "
              f"{100 * t_final.at_cap.mean():.0f}% of trades needed more than the cap (sized down, never a wider stop).\n")

    # reference cases per variant
    md += ["## Reference cases (section 8.7)\n", refcases(df, refraw, keep)]
    (REP / "final.md").write_text("\n".join(md), encoding="utf-8")
    print(tab[["trades", "win%", "avgR", "IS_avgR", "OOS_avgR", "HO_avgR"]].to_string())


def refcases(df, raw, keep) -> str:
    out = ["| Case | Variant | Detected? | Entry | Stop | Filters failed (final set) | R |", "|---|---|---|---|---|---|---|"]
    for lab, sym, lvl, a, b in REFS:
        a, b = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC") + pd.Timedelta(days=1)
        for rv in ("R1", "R2", "R3d", "R3w"):
            near = lambda d: d[(d.symbol == sym) & (d.reclaim_variant == rv) & (d.entry_variant == "E1")  # noqa: E731
                               & ((d.level - lvl).abs() / lvl <= 0.02)
                               & (pd.to_datetime(d.swept_time, utc=True) >= a) & (pd.to_datetime(d.swept_time, utc=True) < b)]
            e = near(df[df.side == "long"]).sort_values("entry_time")
            r = near(raw)
            if len(e):
                x = e.iloc[0]
                failed = [f for f in keep if not bool(x[f])]
                out.append(f"| {lab} | {rv}/E1 | yes (L={x.level:g}, swept {x.swept_low:g} {pd.Timestamp(x.swept_time):%d %b %H:%M}) | "
                           f"{x.entry_time:%d %b %H:%M} @ {x.entry:g} | {x.stop:g} ({100 * x.stop_pct:.1f}%) | "
                           f"{', '.join(failed) or 'none - TRADE'}{' [tier ' + str(x.tier) + ']'} | {x['R_partial_1r_be']:.2f} |")
            elif len(r):
                out.append(f"| {lab} | {rv}/E1 | skipped: {', '.join(sorted(set(r.skipped.astype(str))))} | | | | |")
            else:
                why = _why(raw, sym, lvl, a, b, rv)
                out.append(f"| {lab} | {rv}/E1 | no | | | {why} | |")
    return "\n".join(out) + "\n"


def _why(raw, sym, lvl, a, b, rv) -> str:
    any_lv = raw[(raw.symbol == sym) & (pd.to_datetime(raw.swept_time, utc=True) >= a) & (pd.to_datetime(raw.swept_time, utc=True) < b)]
    if any_lv.empty:
        return "no level sweep detected in the window (level not in the validated set, or acceptance/depth rule hit)"
    lv = ", ".join(f"{x:g}" for x in sorted(any_lv.level.unique())[:6])
    return f"no {rv} reclaim of a level within 2%; levels swept then: {lv}"


if __name__ == "__main__":
    main()
