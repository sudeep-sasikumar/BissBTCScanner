"""Backtest the scanner strategy exactly as configured (config.yaml -> scanner + sizing) and export the
dashboard's backtest file.

  python scripts/u12_strategy.py [tag] [n_orderings]     # default: main 200
  -> reports/strategy.md, biss/web/backtest.json

The signal tag must have been generated with the same sweep settings as config.yaml (min 0.3 x ATR4h,
weekend skip): "main" was. Account: $1,000, mode (a), n random within-week orderings. The "median route" is
the ordering whose end balance is the median of all orderings; its trades are exported with the balance
after each close.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.analysis import brackets, enrich, load_signals, trades  # noqa: E402
from biss.metrics import stats, to_md  # noqa: E402
from biss.portfolio import simulate  # noqa: E402

cfg = config.load()
REP = config.ROOT / "reports"
OUT = config.ROOT / "biss" / "web" / "backtest.json"
START = 1000.0


def strategy_trades(df: pd.DataFrame) -> pd.DataFrame:
    sc = cfg.scanner
    rf = sc.required_filters
    sides = ["long", "short"] if sc.shorts else ["long"]
    parts = []
    for side in sides:
        flt = list(rf[side]) if isinstance(rf, dict) else list(rf)
        parts.append(trades(df, reclaim=sc.reclaim, entry=sc.entry, side=side, tiers=list(sc.tiers), filters=flt))
    return pd.concat(parts).sort_values("entry_time")


def ratios(j: pd.DataFrame, start: float) -> dict:
    """Account ratios from the median route's closed-trade balances (daily series)."""
    j = j.sort_values("exit_date")
    bal = pd.Series(j["closed_balance_after"].to_numpy(float), index=pd.to_datetime(j["exit_date"], utc=True))
    bal = bal.groupby(bal.index.floor("D")).last()
    days = pd.date_range(pd.to_datetime(j["entry_date"], utc=True).min().floor("D"), bal.index.max(), freq="D")
    eq = bal.reindex(days).ffill().fillna(start)
    ret = eq.pct_change().fillna(eq.iloc[0] / start - 1)
    years = len(eq) / 365.0
    cagr = (eq.iloc[-1] / start) ** (1 / years) - 1 if years > 0 and eq.iloc[-1] > 0 else -1.0
    sd = ret.std(ddof=1)
    down = np.sqrt(np.mean(np.minimum(ret.to_numpy(), 0.0) ** 2))
    peak = eq.cummax()
    mdd = float((1 - eq / peak).max())
    r = j["R"].astype(float)
    wins, losses = r[r > 0], r[r <= 0]
    pnl = j["pnl_usd"].astype(float)
    return {
        "sharpe": float(ret.mean() / sd * math.sqrt(365)) if sd > 0 else None,
        "sortino": float(ret.mean() / down * math.sqrt(365)) if down > 0 else None,
        "cagr": float(cagr), "max_dd": mdd, "calmar": float(cagr / mdd) if mdd > 0 else None,
        "profit_factor": float(pnl[pnl > 0].sum() / -pnl[pnl < 0].sum()) if (pnl < 0).any() else None,
        "win_rate": float((r > 0).mean()), "avg_R": float(r.mean()), "median_R": float(r.median()),
        "avg_win_R": float(wins.mean()) if len(wins) else None, "avg_loss_R": float(losses.mean()) if len(losses) else None,
        "payoff": float(wins.mean() / -losses.mean()) if len(wins) and len(losses) and losses.mean() < 0 else None,
        "r_sharpe": float(r.mean() / r.std(ddof=1)) if r.std(ddof=1) > 0 else None,
        "r_sortino": float(r.mean() / np.sqrt(np.mean(np.minimum(r.to_numpy(), 0) ** 2))) if (r < 0).any() else None,
        "equity_curve": [[d.strftime("%Y-%m-%d"), round(float(v), 2)] for d, v in eq.items()],
    }


def main(tag: str = "main", n: int = 200) -> None:
    df = enrich(load_signals(tag), cfg)
    t = strategy_trades(df)
    br = brackets()
    rp = float(cfg.sizing.default_risk)
    rng = np.random.default_rng(cfg.validation.seed)
    runs = []
    for _ in range(n):
        key = rng.random(len(t))
        res = simulate(t, rp, cfg, br, "a", order_key=key, start_equity=START)
        runs.append((res["end"], res["max_dd"], res["taken"], key))
    ends = np.array([x[0] for x in runs])
    dds = np.array([x[1] for x in runs])
    taken = np.array([x[2] for x in runs])
    mid = int(np.argsort(ends)[len(ends) // 2])
    med = simulate(t, rp, cfg, br, "a", order_key=runs[mid][3], start_equity=START, keep_journal=True)
    j = med["journal"]
    # enrich the journal with the fields the dashboard shows
    tt = t.reset_index(drop=True)
    extra = tt[["symbol", "entry_time", "side", "tp1_eff", "tp2", "level", "pivot_tf", "risk_mult", "conviction",
                "swept_low", "rr_tp2", "hold_days"]]
    j = j.merge(extra, left_on=["symbol", "entry_date"], right_on=["symbol", "entry_time"], how="left",
                suffixes=("", "_t")).drop(columns=["entry_time"])
    rt = ratios(j, START)
    s_all = stats(t)
    summary = {
        "tag": tag, "orderings": n, "start": START, "risk_pct": rp, "signals": int(len(t)),
        "long_signals": int((t.side == "long").sum()), "short_signals": int((t.side == "short").sum()),
        "first": str(t.entry_time.min())[:10], "last": str(t.entry_time.max())[:10],
        "median_end": float(np.median(ends)), "p10_end": float(np.percentile(ends, 10)),
        "p90_end": float(np.percentile(ends, 90)), "median_dd": float(np.median(dds)),
        "p90_dd": float(np.percentile(dds, 90)), "median_taken": float(np.median(taken)),
        "route_end": float(med["end"]), "route_dd": float(med["max_dd"]), "route_taken": int(med["taken"]),
        "route_skipped": med["skipped"], "route_avg_lev": med["avg_lev"], "route_max_lev": med["max_lev"],
        "signal_stats": {k: ((float(v) if math.isfinite(float(v)) else None)
                             if isinstance(v, (int, float, np.floating, np.integer)) else v) for k, v in s_all.items()},
        "by_side": {sd: {"n": int((t.side == sd).sum()), "win": float((t[t.side == sd].R > 0).mean()),
                         "avg_R": float(t[t.side == sd].R.mean())} for sd in ("long", "short") if (t.side == sd).any()},
        "by_tier": {tr: {"n": int((t.tier == tr).sum()), "win": float((t[t.tier == tr].R > 0).mean()),
                         "avg_R": float(t[t.tier == tr].R.mean())} for tr in ("T1", "T2") if (t.tier == tr).any()},
        "by_slice": {sl: {"n": int((t.slice == sl).sum()), "avg_R": float(t[t.slice == sl].R.mean())}
                     for sl in ("IS", "OOS", "HO") if (t.slice == sl).any()},
        "end_distribution": sorted(round(float(e), 2) for e in ends),
    }
    summary.update({k: v for k, v in rt.items() if k != "equity_curve"})
    cols = ["coin", "symbol", "side", "tier", "entry_date", "entry", "stop", "stop_pct", "tp1_eff", "tp2", "level",
            "level_tf", "conviction", "risk_mult", "leverage", "margin_usd", "risk_usd", "result", "exit_date",
            "exit_price", "R", "pnl_usd", "fees_usd", "funding_usd", "closed_balance_after", "hold_days"]
    rows = j[[c for c in cols if c in j.columns]].copy()
    for c in ("entry_date", "exit_date"):
        rows[c] = pd.to_datetime(rows[c], utc=True).dt.strftime("%Y-%m-%d %H:%M")
    rows = rows.sort_values("entry_date")
    payload = {"summary": summary, "equity_curve": rt["equity_curve"],
               "trades": json.loads(rows.to_json(orient="records", double_precision=6))}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    side_tab = pd.DataFrame({f"{sd} {tr}": stats(t[(t.side == sd) & (t.tier == tr)])
                             for sd in ("long", "short") for tr in ("T1", "T2")
                             if ((t.side == sd) & (t.tier == tr)).any()}).T
    md = [f"# Strategy backtest ({tag}, {n} orderings)\n",
          f"Scanner profile in config.yaml: {cfg.scanner.reclaim}/{cfg.scanner.entry}, tiers {list(cfg.scanner.tiers)}, "
          f"filters {dict(cfg.scanner.required_filters)}, risk {rp:.0%} x conviction, open-risk cap "
          f"{cfg.sizing.max_open_risk:.0%}, cluster cap {cfg.sizing.get('max_per_cluster')}.\n",
          f"Signals {len(t)} ({summary['long_signals']} long, {summary['short_signals']} short), "
          f"{summary['first']} to {summary['last']}.\n",
          f"$1,000 start: median end ${summary['median_end']:,.0f}, worst 10% ${summary['p10_end']:,.0f}, "
          f"best 10% ${summary['p90_end']:,.0f}; median max drawdown {summary['median_dd']:.0%} "
          f"(worst 10% {summary['p90_dd']:.0%}); median trades taken {summary['median_taken']:.0f}.\n",
          f"Median route: end ${med['end']:,.0f}, max drawdown {med['max_dd']:.0%}, taken {med['taken']}, "
          f"skipped {med['skipped']}, Sharpe {rt['sharpe']:.2f}, Sortino {rt['sortino']:.2f}, "
          f"CAGR {rt['cagr']:.0%}.\n", "## Per side and tier\n", to_md(side_tab)]
    (REP / "strategy.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[2:5]))
    print(side_tab[["trades", "win%", "avgR"]].to_string())
    print("by slice", summary["by_slice"])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "main", int(sys.argv[2]) if len(sys.argv) > 2 else 200)
