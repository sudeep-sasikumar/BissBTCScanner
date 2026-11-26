"""TradeFi study (section 3.3 / tier T4), reported separately from crypto.

Pool: WEEX TradFi contracts with >= $1M median daily volume (30d). T4 proper: >= $20M (config floor).
Data: underlying daily history from Yahoo (2019 ->), because the perps only list in 2026.
Engine: daily sweep of a weekly level, daily close back above within 14 days (R3d-style), stop 1% below the
swept low, 50% @1R + BE, rest to the 120-day high. Gaps fill at the open. Costs: WEEX taker 0.08%, maker
0.02% on targets, 0.1% slippage, funding assumed 0.01% per 8h against longs.
Filters tested: drawdown band 10-30%, S&P 500 regime (SPY > 200d and 50d > 200d), FOMC +-7d, earnings
within 2 sessions, level validation move 20% vs 10%.
Writes reports/tradfi.md and reports/tables/tradfi_*.csv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.baselines import refined_weekly  # noqa: E402
from biss.data import yahoo  # noqa: E402
from biss.indicators import btc_regime  # noqa: E402
from biss.metrics import stats, to_md  # noqa: E402

cfg = config.load()
REP = config.ROOT / "reports"
CACHE = config.data_dir(cfg) / "yahoo"
SPLIT = pd.Timestamp(cfg.validation.split_date, tz="UTC")


def main() -> None:
    u = pd.read_csv(REP / "universe.csv", keep_default_na=False, na_values={"median_daily_vol_30d_usd": [""]})
    t = u[(u.asset_class != "crypto") & (u.median_daily_vol_30d_usd >= 1e6)].copy()
    t["ticker"] = t.base.map(yahoo.ticker_for)
    t["T4"] = t.median_daily_vol_30d_usd >= cfg.universe.liquidity_floor_usd
    spy = yahoo.daily("SPY", "2018-01-01", CACHE)
    spy_bull = btc_regime(spy.asfreq("D").ffill(), cfg.filters.regime_flip_days)
    rows, cover = [], []
    for r in t.itertuples():
        if not isinstance(r.ticker, str) or not r.ticker:
            cover.append({"symbol": r.symbol, "ticker": "", "bars": 0, "note": "no listed underlying"})
            continue
        d = yahoo.daily(r.ticker, "2019-01-01", CACHE)
        cover.append({"symbol": r.symbol, "ticker": r.ticker, "bars": len(d),
                      "first": d.index[0].date() if len(d) else None})
        if len(d) < 300:
            continue
        earn = yahoo.earnings_dates(r.ticker, CACHE) if r.asset_class == "stock" else []
        for mm in (0.20, 0.10):
            for sig in refined_weekly(r.symbol, d, spy_bull, cfg.data.start, fee=0.0008, maker=0.0002,
                                      dd_band=tuple(cfg.filters.dd_tradfi), daily_sweep=True, use_regime=False,
                                      use_fomc=False, slip=cfg.costs.slippage.T4,
                                      funding_8h=cfg.costs.tradfi_funding_assumption_8h, min_move=mm):
                sig.update({"min_move": mm, "asset_class": r.asset_class, "ticker": r.ticker, "T4": r.T4})
                if earn:
                    bd = [abs(np.busday_count(sig["entry_time"].date(), e.date())) for e in earn]
                    sig["near_earnings"] = min(bd) <= cfg.filters.earnings_sessions
                    sig["earnings_known"] = True
                else:
                    sig["near_earnings"] = False
                    sig["earnings_known"] = r.asset_class != "stock"
                rows.append(sig)
    df = pd.DataFrame(rows)
    pd.DataFrame(cover).to_csv(REP / "tables" / "tradfi_coverage.csv", index=False)
    df.to_csv(REP / "tables" / "tradfi_signals.csv", index=False)
    df["slice"] = np.where(df.entry_time < SPLIT, "IS", "OOS")

    def row(x):
        s = stats(x) if len(x) else {"trades": 0}
        out = {k: s.get(k) for k in ("trades", "win%", "loss%", "avgR", "medR", "PF", "maxLossStreak", "medHold_d")}
        for sl in ("IS", "OOS"):
            y = x[x.slice == sl]
            out[f"{sl}_n"], out[f"{sl}_avgR"] = len(y), round(y.R.mean(), 3) if len(y) else np.nan
        return out

    base = df[(df.min_move == 0.20)]
    grid = {
        "all sweeps (no filters)": base,
        "F2 drawdown 10-30%": base[base.f_dd],
        "F2 + no FOMC +-7d": base[base.f_dd & ~base.near_fomc],
        "F2 + FOMC + no earnings +-2 sessions": base[base.f_dd & ~base.near_fomc & ~base.near_earnings],
        "  ... + S&P not bull": base[base.f_dd & ~base.near_fomc & ~base.near_earnings & ~base.btc_bull],
        "  ... + S&P bull only": base[base.f_dd & ~base.near_fomc & ~base.near_earnings & base.btc_bull],
        "  ... + stop<=12%": base[base.f_dd & ~base.near_fomc & ~base.near_earnings & (base.stop_pct <= 0.12)],
        "level move 10% instead of 20%, F2+FOMC+earn": df[(df.min_move == 0.10) & df.f_dd & ~df.near_fomc & ~df.near_earnings],
    }
    full = base[base.f_dd & ~base.near_fomc & ~base.near_earnings]
    for cls, x in full.groupby("asset_class"):
        grid[f"class {cls} (F2+FOMC+earn)"] = x
    grid["T4 contracts only (>= $20M/day)"] = full[full.T4]
    g = pd.DataFrame({k: row(v) for k, v in grid.items()}).T
    g.to_csv(REP / "tables" / "tradfi_grid.csv")
    md = ["# TradeFi study (T4 and wider pool) - reported separately from crypto\n",
          f"Pool: {len(t)} WEEX TradFi contracts with >= $1M median daily volume; {int(t.T4.sum())} pass the "
          f"${cfg.universe.liquidity_floor_usd/1e6:.0f}M floor (T4: {', '.join(t[t.T4].symbol)}). "
          f"Underlying daily history from Yahoo Finance; {sum(1 for c in cover if c['bars'] >= 300)} with enough history.\n",
          "Engine: daily sweep of a validated weekly level, daily close back above within 14 days, entry at that close, "
          "stop 1% below the swept low, 50% at +1R then stop to entry, rest to the 120-day high. Gaps through the stop "
          "fill at the open. Costs: 0.08% taker / 0.02% maker, 0.1% slippage, assumed funding 0.01%/8h.\n",
          to_md(g), "\n"]
    (REP / "tradfi.md").write_text("\n".join(md), encoding="utf-8")
    print(g[["trades", "win%", "avgR", "IS_avgR", "OOS_avgR"]].to_string())


if __name__ == "__main__":
    main()
