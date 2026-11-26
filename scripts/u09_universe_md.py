"""Output A: reports/universe.md from reports/universe.csv, history_depth.csv and tradfi_hours.csv.
Current liquidity tier uses WEEX's own 30-day volume (today); backtest tiers are point-in-time on Binance."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.metrics import to_md  # noqa: E402

cfg = config.load()
REP = config.ROOT / "reports"


def main() -> None:
    u = pd.read_csv(REP / "universe.csv", keep_default_na=False, na_values={"median_daily_vol_30d_usd": [""]})
    for c in ("median_daily_vol_30d_usd", "vol_30d_usd", "max_leverage", "taker_fee", "maker_fee", "weex_daily_bars"):
        u[c] = pd.to_numeric(u[c], errors="coerce")
    floor = cfg.universe.liquidity_floor_usd
    cr = u[u.asset_class == "crypto"].sort_values("vol_30d_usd", ascending=False).reset_index(drop=True)
    cr["tier_now"] = np.where(cr.base.isin(cfg.universe.t1), "T1",
                              np.where(cr.index < cfg.universe.t2_top_n, "T2",
                                       np.where(cr.median_daily_vol_30d_usd >= floor, "T3", "below floor")))
    tf = u[u.asset_class != "crypto"].copy()
    tf["tier_now"] = np.where(tf.median_daily_vol_30d_usd >= floor, "T4", "below floor")
    allu = pd.concat([cr, tf])
    allu.to_csv(REP / "universe_tiers.csv", index=False)
    md = ["# WEEX USDT-M universe (section 3.1), pulled 25 Nov 2026\n",
          "Source: `GET /capi/v3/market/exchangeInfo`, `/riskLimits`, `/ticker/24hr`, `/klines` (all verified live). "
          "Full per-contract table: `reports/universe_tiers.csv` (symbol, class, listing date, max leverage, brackets, "
          "tick, min size, maker/taker fee, funding interval, 30-day volume, Binance history symbol, tier).\n",
          "## Contracts by class\n"]
    g = allu.groupby("asset_class").agg(contracts=("symbol", "size"),
                                        with_binance_history=("binance_symbol", lambda s: (s != "").sum()),
                                        median_vol_30d_m=("median_daily_vol_30d_usd", lambda s: round(s.median() / 1e6, 2)),
                                        pass_20m_floor=("median_daily_vol_30d_usd", lambda s: int((s >= floor).sum())),
                                        median_max_lev=("max_leverage", "median"),
                                        taker_fee=("taker_fee", "median"), maker_fee=("maker_fee", "median"))
    md.append(to_md(g) + "\n")
    md.append("## Tiers today (WEEX 30-day volume)\n")
    md.append(to_md(allu.groupby(["asset_class", "tier_now"]).size().unstack(fill_value=0)) + "\n")
    md.append("## T1 and the 5 TradeFi contracts that pass the floor\n")
    cols = ["symbol", "asset_class", "listing_date", "max_leverage", "bracket1_cap_usd", "bracket1_mmr", "taker_fee",
            "maker_fee", "funding_interval_h", "median_daily_vol_30d_usd", "binance_symbol"]
    sel = allu[(allu.tier_now.isin(["T1", "T4"]))][cols].copy()
    sel["median_daily_vol_30d_usd"] = (sel["median_daily_vol_30d_usd"] / 1e6).round(1)
    md.append(to_md(sel.set_index("symbol")) + "\n")
    md.append("## History depth on WEEX (first bar served by historyKlines)\n")
    hd = pd.read_csv(REP / "history_depth.csv")
    md.append(to_md(hd.set_index("symbol")[[c for c in hd.columns if c.startswith("weex_first") or c.startswith("binance_first")]]) + "\n")
    md.append("WEEX has no 1M interval (allowed: 1m..1w); monthly bars are built from daily. WEEX 15m/1m starts "
              "Oct 2023 even for BTC/ETH, most alts Oct 2023 or later, TradeFi Jan 2026 or later -> the backtest uses "
              "Binance USDT-M history (data.binance.vision, delisted contracts included) for crypto, mapped by base asset. "
              f"{int((cr.binance_symbol == '').sum())} WEEX crypto contracts have no Binance history and are not testable.\n")
    md.append("## TradeFi when the underlying market is closed (WEEX 1h bars, last 40 days)\n")
    th = pd.read_csv(REP / "tradfi_hours.csv")
    md.append(to_md(th.set_index("symbol")) + "\n")
    md.append("Finding: WEEX TradeFi perps trade 24/7 on their own book (no frozen or flat bars on weekends, except "
              "near-dead CEG). Weekend ranges are about 1/4 of the US cash session and volume about 1/5-1/10, and the "
              "move from the Friday close to the Monday US open reached 2-10%. So a weekend 'sweep' happens on thin "
              "volume, and a stop can be jumped at the Monday open. The backtest fills such stops at the first price "
              "beyond the stop (bar open).\n")
    (REP / "universe.md").write_text("\n".join(md), encoding="utf-8")
    print("wrote reports/universe.md")


if __name__ == "__main__":
    main()
