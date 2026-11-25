"""Section 7: position size from risk, leverage as an output, WEEX caps and liquidation buffer.

Isolated margin, linear USDT perp. For a long with initial margin ratio im = 1/lev and maintenance margin
ratio mmr, liquidation sits about (im - mmr) below entry. Requirement: liquidation beyond the stop by at
least liq_buffer_mult x stop distance  =>  im - mmr >= (1 + mult) * stop_pct  =>
lev <= 1 / ((1 + mult) * stop_pct + mmr).
"""
from __future__ import annotations

import math


def mmr_for(brackets: list[dict] | None, notional: float, default_mmr: float = 0.01) -> tuple[float, int]:
    """(maintenance margin ratio, bracket max leverage) for a notional; WEEX riskLimits brackets."""
    if not brackets:
        return default_mmr, 20
    for b in brackets:
        if float(b["notionalFloor"]) <= notional < float(b["notionalCap"]):
            return float(b["maintMarginRatio"]), int(b["initialLeverage"])
    b = brackets[-1]
    return float(b["maintMarginRatio"]), int(b["initialLeverage"])


def lev_cap(base: str, asset_class: str, caps: dict, weex_max: int | None) -> float:
    if asset_class != "crypto":
        mine = caps["tradfi"]
    else:
        mine = caps.get(base, caps["crypto"])
    return float(min(mine, weex_max)) if weex_max else float(mine)


def liq_price_frac(lev: float, mmr: float) -> float:
    """Adverse move (fraction of entry) to liquidation for isolated margin."""
    return 1.0 / lev - mmr


def size(equity: float, free_margin: float, risk_pct: float, stop_pct: float, cap: float,
         brackets: list[dict] | None, liq_mult: float) -> dict:
    """Returns notional, margin, leverage and flags. Size is cut (never the stop widened) when the cap,
    liquidation buffer or free margin can't support the full risk."""
    risk_usd = equity * risk_pct
    notional = risk_usd / stop_pct
    mmr, bmax = mmr_for(brackets, notional)
    need_lev = 1.0 / ((1 + liq_mult) * stop_pct + mmr)
    lev = min(cap, bmax, need_lev)
    lev = max(lev, 1.0) if need_lev >= 1.0 else need_lev
    at_cap = need_lev > min(cap, bmax)
    margin = notional / lev
    shrunk = False
    if margin > free_margin:
        shrunk = True
        margin = max(free_margin, 0.0)
        notional = margin * lev
    liq_frac = liq_price_frac(lev, mmr_for(brackets, notional)[0]) if lev > 0 else math.inf
    return {"notional": notional, "margin": margin, "lev": lev, "need_lev": need_lev, "at_cap": at_cap,
            "shrunk": shrunk, "risk_usd": notional * stop_pct, "liq_frac": liq_frac,
            "liq_buffer_ok": liq_frac >= (1 + liq_mult) * stop_pct - 1e-12}
