"""Account simulation (sections 7 and 8.6).

Mode (a): every signal, equal small risk, total open risk <= max_open_risk, <= max_per_cluster concurrent
positions per correlated cluster (null = no cap), one position per symbol (and side when
one_per_symbol_side), margin must be free. Mode (b): his challenge rule, one position at a time,
first fill wins, 20-50% risk (stress test only).

P&L of a trade = net R x the risk actually taken (R already includes fees, slippage and funding). If the
trade's worst excursion reaches the liquidation price, the whole margin is lost instead.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .sizing import size

US_TECH = {"AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD", "AVGO", "ORCL", "PLTR", "MU", "INTC",
           "TSM", "QCOM", "ARM", "NFLX", "CRM", "ADBE", "MSTR", "COIN", "HOOD", "SMCI", "ASML", "QQQ", "TQQQ",
           "SOXL", "SOXS", "SMH", "SOXX", "NAS100", "XLK"}


def cluster_of(base: str, asset_class: str) -> str:
    if asset_class == "crypto":
        return "crypto_majors" if base in ("BTC", "ETH") else "crypto_alts"
    if asset_class == "stock":
        return "us_tech" if base in US_TECH else "stocks_other"
    return asset_class


def simulate(trades: pd.DataFrame, risk_pct: float, cfg, brackets: dict, mode: str = "a",
             order_key: np.ndarray | None = None, start_equity: float = 1000.0, keep_journal: bool = False) -> dict:
    sz = cfg.sizing
    if trades.empty:
        return {"end": start_equity, "max_dd": 0.0, "taken": 0, "skipped": {}, "journal": pd.DataFrame()}
    tr = trades.reset_index(drop=True)
    et = tr["entry_time"].to_numpy("datetime64[ns]")
    xt = tr["exit_time"].to_numpy("datetime64[ns]")
    if order_key is None:
        order = np.argsort(et, kind="stable")
    else:
        week = (et.astype("int64") // (7 * 86400 * 10**9))
        order = np.lexsort((order_key, week))
    bal = start_equity
    peak = bal
    max_dd = 0.0
    open_: list[dict] = []
    skipped: dict[str, int] = {}
    jr = []
    cap_hits = shrunk = 0
    levs = []

    def close_until(t):
        nonlocal bal, peak, max_dd
        open_.sort(key=lambda p: p["exit"])
        while open_ and open_[0]["exit"] <= t:
            p = open_.pop(0)
            bal += p["pnl"]
            peak = max(peak, bal)
            max_dd = max(max_dd, 1 - bal / peak if peak > 0 else 1)
            if p["j"] is not None:
                p["j"]["closed_balance_after"] = bal

    recs = tr.to_dict("records")
    for i in order:
        r = recs[i]
        close_until(et[i])
        if bal <= 1e-6:
            skipped["bust"] = skipped.get("bust", 0) + 1
            continue
        mult = float(r.get("risk_mult", 1.0))
        rp = risk_pct * mult
        if mode == "b":
            if open_:
                skipped["busy"] = skipped.get("busy", 0) + 1
                continue
        else:
            open_risk = sum(p["risk"] for p in open_) / bal
            if open_risk + rp > sz.max_open_risk + 1e-9:
                skipped["open_risk_cap"] = skipped.get("open_risk_cap", 0) + 1
                continue
            cl = r["cluster"]
            if sz.get("max_per_cluster") and sum(1 for p in open_ if p["cluster"] == cl) >= sz.max_per_cluster:
                skipped["cluster_cap"] = skipped.get("cluster_cap", 0) + 1
                continue
            per_side = bool(sz.get("one_per_symbol_side"))
            if any(p["symbol"] == r["symbol"] and (not per_side or p["side"] == r["side"]) for p in open_):
                skipped["same_symbol"] = skipped.get("same_symbol", 0) + 1
                continue
        free = bal - sum(p["margin"] for p in open_)
        if free <= 1e-6:
            skipped["no_margin"] = skipped.get("no_margin", 0) + 1
            continue
        s = size(bal, free, rp, float(r["stop_pct"]), float(r["lev_cap"]), brackets.get(r["weex_symbol"]),
                 sz.liq_buffer_mult)
        if s["notional"] <= 0:
            skipped["no_margin"] = skipped.get("no_margin", 0) + 1
            continue
        cap_hits += s["at_cap"]
        shrunk += s["shrunk"]
        levs.append(s["lev"])
        liquidated = float(r["mae_frac"]) >= s["liq_frac"]
        if liquidated:
            pnl = -s["margin"] - s["notional"] * float(r["fees_frac"])
        else:
            pnl = float(r["R"]) * s["risk_usd"]
        j = None
        if keep_journal:
            j = {"coin": r["base"], "symbol": r["symbol"], "entry_date": r["entry_time"],
                 "entry": r["entry"], "stop": r["stop"], "stop_pct": r["stop_pct"], "target": r["tp2"],
                 "leverage": round(s["lev"], 2), "margin_usd": round(s["margin"], 2),
                 "result": "liquidated" if liquidated else r["outcome"], "exit_date": r["exit_time"],
                 "exit_price": r["exit_price"], "trade_return_pct": round(100 * pnl / s["margin"], 2) if s["margin"] else 0,
                 "pnl_usd": round(pnl, 2), "closed_balance_after": None, "asset_class": r["asset_class"],
                 "tier": r["tier"], "level_tf": r["level_tf"], "reclaim_variant": r["reclaim_variant"],
                 "funding_usd": round(-float(r["funding_frac"]) * s["notional"], 2),
                 "fees_usd": round(float(r["fees_frac"]) * s["notional"], 2), "R": round(float(r["R"]), 3),
                 "risk_usd": round(s["risk_usd"], 2), "at_cap": s["at_cap"], "shrunk": s["shrunk"]}
            jr.append(j)
        open_.append({"exit": xt[i], "pnl": pnl, "risk": s["risk_usd"], "margin": s["margin"],
                      "cluster": r["cluster"], "symbol": r["symbol"], "side": r.get("side", "long"), "j": j})
    close_until(np.datetime64("2262-01-01"))
    return {"end": bal, "max_dd": max_dd, "taken": len(levs), "skipped": skipped,
            "cap_hits": cap_hits, "shrunk": shrunk, "avg_lev": float(np.mean(levs)) if levs else 0.0,
            "max_lev": float(np.max(levs)) if levs else 0.0,
            "journal": pd.DataFrame(jr) if keep_journal else None}


def shuffles(trades: pd.DataFrame, risk_pct: float, cfg, brackets: dict, n: int, seed: int, mode: str = "a") -> dict:
    rng = np.random.default_rng(seed)
    ends, dds, taken = [], [], []
    for _ in range(n):
        res = simulate(trades, risk_pct, cfg, brackets, mode, order_key=rng.random(len(trades)))
        ends.append(res["end"])
        dds.append(res["max_dd"])
        taken.append(res["taken"])
    ends, dds = np.array(ends), np.array(dds)
    return {"median_end": float(np.median(ends)), "p10_end": float(np.percentile(ends, 10)),
            "median_dd": float(np.median(dds)), "p90_dd": float(np.percentile(dds, 90)),
            "median_taken": float(np.median(taken))}
