"""Section 8/9 report: variant grid per tier, baselines, management variants, ablation, shorts, level types,
years, concentration, path-dependence, mode (b), leverage, reference cases, frequency, journal.

Writes reports/backtest.md, reports/tables/*.csv, reports/journal.csv.
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
TAB.mkdir(parents=True, exist_ok=True)
TIERS = ["T1", "T2", "T3", "T4", "T4pool"]
KEYS = ["trades", "win%", "loss%", "scratch%", "avgR", "medR", "PF", "maxLossStreak", "maxDD_R", "medHold_d",
        "exposure", "avg_stop%", "avg_lev_need", "max_lev_need", "at_cap%", "funding_R", "fees_R_avg"]
md: list[str] = []


def sec(title: str, text: str = "") -> None:
    md.append(f"\n## {title}\n")
    if text:
        md.append(text + "\n")


def slice_cols(t: pd.DataFrame) -> dict:
    out = {}
    for s in ("IS", "OOS", "HO"):
        x = t[t["slice"] == s]
        out[f"{s}_n"] = len(x)
        out[f"{s}_avgR"] = round(x["R"].mean(), 3) if len(x) else np.nan
    return out


def row(t: pd.DataFrame) -> dict:
    s = stats(t) if len(t) else {"trades": 0}
    r = {k: s.get(k, np.nan) for k in KEYS}
    r.update(slice_cols(t) if len(t) else {})
    return r


def write(name: str, df: pd.DataFrame, note: str = "") -> None:
    df.to_csv(TAB / f"{name}.csv")
    md.append((note + "\n\n" if note else "") + to_md(df) + "\n")


def main() -> None:
    raw = load_signals("main", keep_skipped_for={r[1] for r in REFS})
    refraw = raw[raw.symbol.isin({r[1] for r in REFS}) & (raw.side == "long")].copy()
    df = enrich(raw, cfg)
    n_1m = raw.groupby("symbol")[["n_1m_calls", "n_1m_missing"]].max().sum() if "n_1m_calls" in raw else None
    del raw
    md.append("# Backtest report: HTF sweep -> LTF reclaim (WEEX universe, Binance history)\n")
    md.append(f"Generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC. Signals {df.entry_time.min():%Y-%m-%d} to "
              f"{df.entry_time.max():%Y-%m-%d}. Raw simulated signals: {len(df):,} on {df.symbol.nunique()} symbols. "
              f"Slices: IS = before {cfg.validation.split_date}, OOS = after, HO = {int(100*cfg.validation.holdout_frac)}% of "
              f"symbols held out of design (all dates). Ambiguous 15m bars resolved with 1m: "
              f"{'' if n_1m is None else f'{int(n_1m.n_1m_calls)} lookups, {int(n_1m.n_1m_missing)} without 1m data (stop assumed first)'}.\n")

    # ---------- 1. grid ----------
    sec("1. Reclaim x entry grid, longs, all default filters, default management (50% @1R, BE, rest to TP2)")
    grid = {}
    for tier in TIERS:
        for rv in ("R1", "R2", "R3d", "R3w"):
            for ev in ("E1", "E2"):
                t = trades(df, reclaim=rv, entry=ev, tiers=[tier])
                grid[(tier, rv, ev)] = t
    g = pd.DataFrame({f"{k[0]} {k[1]}/{k[2]}": row(v) for k, v in grid.items()}).T
    write("grid", g)
    # pick the design variant on IS only (non-holdout, first half), T1+T2 pooled
    cand = {}
    for rv in ("R1", "R2", "R3d", "R3w"):
        for ev in ("E1", "E2"):
            t = trades(df, reclaim=rv, entry=ev, tiers=["T1", "T2"])
            x = t[t["slice"] == "IS"]
            cand[(rv, ev)] = (x["R"].mean() if len(x) >= 20 else -9, len(x))
    best = max(cand, key=lambda k: cand[k][0])
    md.append(f"Design choice (IS slice only, T1+T2, n>=20): **{best[0]}/{best[1]}** "
              f"(IS avgR {cand[best][0]:.3f}, n={cand[best][1]}). Everything below uses it unless stated.\n")

    # ---------- 2. baselines ----------
    sec("2. Baselines")
    b_rows = {}
    for lab, f in (("refined weekly (doc costs)", "baseline_refined_doc.csv"),
                   ("refined weekly (WEEX costs)", "baseline_refined_weex.csv")):
        p = REP / f
        if p.exists():
            b = pd.read_csv(p, parse_dates=["entry_time", "exit_time"])
            b = b[(b["rank"] <= 50) & b["kept"]]
            from biss.tiers import base_of
            from biss.universe import is_holdout
            ho = b.symbol.map(lambda s: is_holdout(base_of(s), cfg.validation.holdout_frac, cfg.validation.seed))
            b["slice"] = np.where(ho, "HO", np.where(b.entry_time < pd.Timestamp(cfg.validation.split_date, tz="UTC"),
                                                     "IS", "OOS"))
            b["hold_days"] = b.get("hold_days", np.nan)
            b_rows[lab] = row(b)
            b_rows[lab + ", stop<=12%"] = row(b[b.stop_pct <= 0.12])
    try:
        rc = enrich(load_signals("ruleC"), cfg)
        for lab, fl in (("rule C 4h, fixed 2R", "fixed_2r"), ("rule C 4h, fixed 3R", "fixed_3r"),
                        ("rule C 4h, 50%@1R+BE", "partial_1r_be")):
            t = trades(rc, mgmt=fl, filters=["F4_location", "min_rr"], tiers=["T1", "T2"])
            b_rows[lab] = row(t)
            t1 = trades(rc, mgmt=fl, filters=["F4_location", "min_rr"], tiers=["T1"])
            b_rows[lab + " (T1 only)"] = row(t1)
    except Exception as e:  # noqa: BLE001
        md.append(f"rule C not available: {e}\n")
    bt = trades(df, reclaim=best[0], entry=best[1], tiers=["T1", "T2"])
    b_rows[f"THIS: {best[0]}/{best[1]} T1+T2"] = row(bt)
    write("baselines", pd.DataFrame(b_rows).T,
          "Documented refined result: 158 trades, 68% win, +0.97R (universe B, 0.05%/side, no funding). "
          "Documented rule C: about -0.1R to +0.03R.")

    # ---------- 3. management ----------
    sec("3. Management variants (best reclaim/entry, longs, T1+T2)")
    mg = {}
    for m in ("partial_1r_be", "fixed_2r", "fixed_3r", "partial_tp1", "trail_4h_hl", "time_stop", "close_below_exit"):
        mg[m] = row(trades(df, mgmt=m, reclaim=best[0], entry=best[1], tiers=["T1", "T2"]))
    write("management", pd.DataFrame(mg).T)

    # ---------- 4. ablation ----------
    sec("4. Ablation: remove one filter at a time (best variant, longs)")
    for tiers in (["T1", "T2"], ["T3"], ["T4"], ["T4pool"]):
        ab = {"all filters": row(trades(df, reclaim=best[0], entry=best[1], tiers=tiers))}
        for f in FILTERS:
            ab[f"without {f}"] = row(trades(df, reclaim=best[0], entry=best[1], tiers=tiers,
                                            filters=[x for x in FILTERS if x != f]))
        ab["no filters"] = row(trades(df, reclaim=best[0], entry=best[1], tiers=tiers, filters=[]))
        ab["max 1 attempt"] = row(trades(df, reclaim=best[0], entry=best[1], tiers=tiers, attempts=1))
        md.append(f"**Tiers {'+'.join(tiers)}**\n")
        write(f"ablation_{'_'.join(tiers)}", pd.DataFrame(ab).T)
        if tiers == ["T1", "T2"]:
            keep = []
            base = ab["all filters"]
            for f in FILTERS:
                w = ab[f"without {f}"]
                helps = all((base.get(f"{s}_avgR", np.nan) > w.get(f"{s}_avgR", np.nan)) for s in ("IS", "OOS", "HO"))
                keep.append({"filter": f, "helps_in_all_3_slices": helps})
            write("filter_verdicts", pd.DataFrame(keep).set_index("filter"),
                  "A filter is kept only if removing it lowers avg R in IS, OOS and HO:")

    # ---------- 5. F1 by group ----------
    sec("5. BTC regime filter by group (best variant, longs, other filters on)")
    others = [x for x in FILTERS if x != "F1_regime"]
    rg = {}
    for lab, sel in (("BTC", lambda d: d[d.base == "BTC"]), ("alts T1+T2", lambda d: d[(d.base != "BTC")])):
        allt = trades(sel(df), reclaim=best[0], entry=best[1], tiers=["T1", "T2"], filters=others)
        rg[f"{lab}: bull regime"] = row(allt[allt.btc_bull])
        rg[f"{lab}: not bull"] = row(allt[~allt.btc_bull])
    write("regime_groups", pd.DataFrame(rg).T)

    # ---------- 6. shorts ----------
    sec("6. Shorts (mirror; F2 is not applied to shorts)")
    sh = {}
    for tier in ("T1", "T2", "T3"):
        for rv in ("R1", "R2"):
            sh[f"{tier} {rv}/E1"] = row(trades(df, reclaim=rv, entry="E1", side="short", tiers=[tier],
                                                filters=[x for x in FILTERS if x not in ("F2_drawdown", "F1_regime")]))
    write("shorts", pd.DataFrame(sh).T)

    # ---------- 7. level types & years ----------
    sec("7. By level type and by year (best variant, longs, T1+T2)")
    lt = {k: row(v) for k, v in bt.groupby("level_type")}
    write("by_level_type", pd.DataFrame(lt).T)
    yr = {str(k): row(v) for k, v in bt.groupby("year")}
    write("by_year", pd.DataFrame(yr).T)
    top = bt.sort_values("R", ascending=False).head(10)[["symbol", "entry_time", "level", "level_type", "R"]]
    md.append(f"Top-10 trades = {top.R.sum():.1f}R of {bt.R.sum():.1f}R total.\n\n" + to_md(top.set_index("symbol")) + "\n")

    # ---------- 8. signal frequency ----------
    sec("8. Signal frequency (raw signals before filters, longs, best variant, attempt 1)")
    fr = df[(df.reclaim_variant == best[0]) & (df.entry_variant == best[1]) & (df.side == "long") & (df.attempt == 1)]
    yrs = max((fr.entry_time.max() - fr.entry_time.min()).days / 365.25, 0.1)
    freq = (fr.groupby(["tier", "level_type"]).size() / yrs).round(1).unstack(fill_value=0)
    write("frequency_per_year", freq)
    fq = (bt.groupby(["tier", "level_type"]).size() / yrs).round(1).unstack(fill_value=0)
    write("frequency_after_filters", fq, "After all filters (trades per year):")

    # ---------- 9. account sims ----------
    sec("9. Account simulation, mode (a): 300 random within-week orderings, $1,000 start")
    br = brackets()
    rows = {}
    for tier_set in (["T1"], ["T2"], ["T1", "T2"], ["T3"], ["T4"], ["T4pool"]):
        t = trades(df, reclaim=best[0], entry=best[1], tiers=tier_set)
        if len(t) < 5:
            continue
        for rp in cfg.sizing.risk_pct:
            s = shuffles(t, rp, cfg, br, cfg.validation.shuffles, cfg.validation.seed)
            rows[f"{'+'.join(tier_set)} @ {int(rp*100)}%"] = {k: round(v, 2) for k, v in s.items()}
    write("path_dependence", pd.DataFrame(rows).T)
    md.append("Mode (b) stress test (one position at a time, first fill wins), T1+T2:\n")
    t = trades(df, reclaim=best[0], entry=best[1], tiers=["T1", "T2"])
    mb = {}
    for rp in (0.2, 0.35, 0.5):
        s = shuffles(t, rp, cfg, br, cfg.validation.shuffles, cfg.validation.seed, mode="b")
        mb[f"mode b @ {int(rp*100)}%"] = {k: round(v, 2) for k, v in s.items()}
    write("mode_b", pd.DataFrame(mb).T)

    # ---------- 10. leverage ----------
    sec("10. Leverage actually needed (liq beyond stop by 1x stop distance)")
    lv = {}
    for rv in ("R1", "R2", "R3d"):
        t = trades(df, reclaim=rv, entry="E1", tiers=["T1", "T2"])
        if len(t):
            lv[rv] = {"trades": len(t), "median_stop%": round(100 * t.stop_pct.median(), 2),
                      "median_lev_needed": round(t.lev_needed.median(), 1),
                      "share_at_cap%": round(100 * t.at_cap.mean(), 1),
                      "avg_lev_cap": round(t.lev_cap.mean(), 1)}
    write("leverage", pd.DataFrame(lv).T)
    res = simulate(trades(df, reclaim=best[0], entry=best[1], tiers=["T1", "T2"]), cfg.sizing.default_risk, cfg, br,
                   keep_journal=True)
    md.append(f"At {int(cfg.sizing.default_risk*100)}% risk (mode a, chronological): taken {res['taken']}, "
              f"skipped {res['skipped']}, sized at a leverage cap {res['cap_hits']}, shrunk for margin {res['shrunk']}, "
              f"avg leverage {res['avg_lev']:.1f}x, max {res['max_lev']:.1f}x, end ${res['end']:,.0f}, "
              f"max DD {100*res['max_dd']:.0f}%.\n")
    jr = res["journal"]
    if jr is not None and len(jr):
        jr.to_csv(REP / "journal.csv", index=False)

    # ---------- 12. mark price ----------
    sec("12. Stops checked against mark price (Binance markPriceKlines 15m, live symbols, T1+T2 trades)")
    md.append(mark_check(trades(df, reclaim=best[0], entry=best[1], tiers=["T1", "T2"])))

    # ---------- 11. reference cases ----------
    sec("11. Reference cases")
    md.append(reference_cases(df, best, refraw))
    (REP / "backtest.md").write_text("\n".join(md), encoding="utf-8")
    print("wrote reports/backtest.md")


def mark_check(t: pd.DataFrame, max_trades: int = 150) -> str:
    """Does the mark price touch the original stop when last price did not (or vice versa)?"""
    import json

    from biss.data import binance

    live = set(json.loads((config.data_dir(cfg) / "binance" / "symbols.json").read_text(encoding="utf-8"))["live"])
    t = t[t.symbol.isin(live)].tail(max_trades)
    n = both = mark_only = last_only = 0
    worst = []
    for r in t.itertuples():
        a = int(r.entry_time.timestamp() * 1000)
        b = int(r.exit_time.timestamp() * 1000)
        try:
            mk = binance.rest_klines(r.symbol, "15m", a, b, kind="markPriceKlines")
        except Exception:  # noqa: BLE001
            continue
        if mk.empty:
            continue
        n += 1
        # path until the first leg: did price reach the ORIGINAL stop?
        mlo = mk["low"].min() if r.side == "long" else -mk["high"].max()
        stop = r.stop if r.side == "long" else -r.stop
        mark_hit = mlo <= stop
        last_hit = r.outcome in ("stop",)
        both += mark_hit and last_hit
        mark_only += mark_hit and not last_hit
        last_only += last_hit and not mark_hit
        worst.append(abs(mlo - (r.entry - r.mae_frac * r.entry if r.side == "long" else -(r.entry + r.mae_frac * r.entry))) / r.entry)
    if not n:
        return "no mark-price data fetched\n"
    return (f"{n} trades checked (most recent {max_trades}). Original stop touched by both last and mark: {both}; "
            f"mark only (last price never hit, mark did - note BE moves can hide these): {mark_only}; last only: {last_only}. "
            f"Median |mark extreme - last extreme| = {100*np.median(worst):.3f}% of entry.\n")


REFS = [
    ("BTC weekly ~58.9k, swept 30 Jun 2026, reclaimed 1 Jul", "BTCUSDT", 58900, "2026-06-28", "2026-07-03"),
    ("HYPE ~52.64, swept 31 Jul 2026, reclaimed 3 Aug", "HYPEUSDT", 52.64, "2026-07-29", "2026-08-06"),
    ("ZEC ~300.8, swept 5 Jun 2026", "ZECUSDT", 300.8, "2026-06-03", "2026-06-12"),
    ("BTC below the lows, back above ~61.5k (17-20 Nov 2026)", "BTCUSDT", 61500, "2026-11-16", "2026-11-22"),
    ("BTC 57.3-57.7k higher-low plan (23 Nov 2026)", "BTCUSDT", 57500, "2026-11-23", "2026-11-26"),
]


def reference_cases(df: pd.DataFrame, best, raw: pd.DataFrame) -> str:
    out = ["| Case | Raw signals near level (any variant) | Best-variant signal | Filters failed | R (default mgmt) |",
           "|---|---|---|---|---|"]
    for lab, sym, lvl, a, b in REFS:
        a, b = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")
        r = raw[(raw.symbol == sym) & (raw.side == "long")]
        r = r[((pd.to_datetime(r.swept_time, utc=True) >= a) & (pd.to_datetime(r.swept_time, utc=True) <= b))]
        near = r[(r.level - lvl).abs() / lvl <= 0.03]
        e = df[(df.symbol == sym) & (df.side == "long") & (df.entry_time >= a) & (df.entry_time <= b + pd.Timedelta(days=2))]
        e = e[(e.level - lvl).abs() / lvl <= 0.03]
        eb = e[(e.reclaim_variant == best[0]) & (e.entry_variant == best[1])]
        raw_txt = "; ".join(sorted({f"{x.reclaim_variant}/{x.entry_variant} L={x.level:g}"
                                    + (f" SKIPPED {x.skipped}" if x.skipped else f" @{pd.Timestamp(x.entry_time):%d %b %H:%M}")
                                    for x in near.itertuples()}))[:400] or "none"
        if len(eb):
            x = eb.iloc[0]
            failed = [f for f in FILTERS if not bool(x[f])]
            out.append(f"| {lab} | {raw_txt} | {x.entry_time:%d %b %H:%M} entry {x.entry:g}, stop {x.stop:g} "
                       f"({100*x.stop_pct:.1f}%), TP2 {x.tp2:g} | {', '.join(failed) or 'none'} | {x['R_partial_1r_be']:.2f} |")
        else:
            why = "no sweep/reclaim of a level within 3% in the window" if near.empty else "see raw column"
            out.append(f"| {lab} | {raw_txt} | missed ({why}) | | |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
