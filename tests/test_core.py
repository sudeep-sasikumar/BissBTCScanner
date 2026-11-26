"""Unit tests for the rules that most easily go wrong: lookahead, bar ordering, gaps, sizing."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from biss import calendar as cal
from biss import config
from biss.levels import LevelSet, pivots
from biss.setups import NS_15M, Bars, find_reclaim
from biss.sizing import size
from biss.trade import simulate


def bars_from(prices: list[tuple[float, float, float, float]], start="2026-01-05") -> Bars:
    """(open, high, low, close) per 15m bar, long direction."""
    a = np.array(prices, float)
    t = pd.date_range(start, periods=len(a), freq="15min", tz="UTC").as_unit("ns").asi8
    close_t = t + NS_15M
    n = len(a)
    return Bars(t, a[:, 0], a[:, 1], a[:, 2], a[:, 3], np.full(n, 1.0), np.full(n, 3.0),
                (close_t % (4 * 3600 * 10**9)) == 0, (close_t % (86400 * 10**9)) == 0, np.zeros(n, bool), 1)


def test_pivot_usable_only_after_validating_move():
    idx = pd.date_range("2024-01-01", periods=20, freq="W-MON", tz="UTC")
    lows = [100, 98, 95, 90, 93, 96, 99, 104, 108, 112, 115, 117, 118, 118, 118, 118, 118, 118, 118, 118]
    df = pd.DataFrame({"open": lows, "high": [x * 1.02 for x in lows], "low": lows,
                       "close": [x * 1.01 for x in lows]}, index=idx)
    pv = [p for p in pivots(df, "W", 2, 0.20, 2.5, 10, 52) if p["kind"] == "pivot_low"]
    assert pv and pv[0]["price"] == 90
    # 90 * 1.2 = 108 -> first high >= 108 is bar 8 (high 108*1.02) ... usable from the NEXT bar
    first_hit = next(i for i, h in enumerate(df["high"]) if i > 3 and h >= 108)
    assert pv[0]["valid_from"] == idx[first_hit + 1]


def test_stop_first_when_bar_hits_both_and_no_1m():
    # entry 100 at bar 0 close, stop 98, 1R = 102; bar 1 touches both 97 and 103
    b = bars_from([(100, 100, 100, 100), (100, 103, 97, 101), (101, 110, 100, 109)])
    r = simulate(b, 0, 100.0, 98.0, 102.0, 108.0, 99.0, "partial_1r_be", 0.0, 0.0, 0.0)
    assert r["outcome"] == "stop" and r["R"] == pytest.approx(-1.0)


def test_resolver_target_first_then_stop_on_rest():
    b = bars_from([(100, 100, 100, 100), (100, 103, 97, 101), (101, 110, 100, 109)])
    r = simulate(b, 0, 100.0, 98.0, 102.0, 108.0, 99.0, "partial_1r_be", 0.0, 0.0, 0.0,
                 resolver=lambda t, s, tg: "tgt")
    # half at +1R, other half stopped at the ORIGINAL stop in the same bar (BE only from next bar)
    assert r["R"] == pytest.approx(0.5 * 1 + 0.5 * -1)


def test_gap_through_stop_fills_at_open():
    b = bars_from([(100, 100, 100, 100), (95, 96, 94, 95)])
    r = simulate(b, 0, 100.0, 98.0, 102.0, 108.0, 99.0, "partial_1r_be", 0.0, 0.0, 0.0)
    assert r["exit_price"] == pytest.approx(95.0)
    assert r["R"] == pytest.approx(-2.5)


def test_partial_be_then_target():
    b = bars_from([(100, 100, 100, 100), (100, 102.5, 99.5, 102), (102, 103, 100.5, 102.5), (103, 109, 102, 108)])
    r = simulate(b, 0, 100.0, 98.0, 102.0, 108.0, 99.0, "partial_1r_be", 0.0, 0.0, 0.0)
    assert r["outcome"] == "target"
    assert r["R"] == pytest.approx(0.5 * 1 + 0.5 * 4)


def test_fees_and_slippage_reduce_R():
    b = bars_from([(100, 100, 100, 100), (100, 100.5, 97, 98)])
    r = simulate(b, 0, 100.0, 98.0, 102.0, 108.0, 99.0, "fixed_2r", 0.0008, 0.0002, 0.001)
    # entry fee+slip 0.18% + stop fee 0.08% + stop slip 0.1% of 98 ~= 0.358% of notional on a 2% stop
    assert r["R"] < -1.15


def test_sizing_liquidation_buffer_and_cap():
    z = size(10_000, 10_000, 0.03, 0.02, cap=10, brackets=None, liq_mult=1.0)
    assert z["notional"] == pytest.approx(15_000)
    # need lev = 1/(2*0.02 + 0.01) = 20 -> capped at 10
    assert z["lev"] == 10 and z["at_cap"]
    assert z["liq_frac"] >= 2 * 0.02
    z2 = size(10_000, 100, 0.03, 0.02, cap=10, brackets=None, liq_mult=1.0)
    assert z2["shrunk"] and z2["margin"] == pytest.approx(100)


def test_r1_reclaim_needs_two_closes_and_window():
    cfg = config.load()
    L = 100.0
    rows = [(101, 101, 99.0, 99.5), (99.5, 99.8, 98.5, 99.0), (99, 100.5, 98.8, 100.2), (100.2, 100.8, 100, 100.6)]
    b = bars_from(rows)
    ev, r, li = find_reclaim(b, L, 0, "R1", cfg, 100)
    assert ev == "reclaim" and r == 3 and li == 1


def test_acceptance_when_too_deep():
    cfg = config.load()
    rows = [(101, 101, 99.0, 99.5), (99.5, 99.6, 90.0, 92.0), (92, 101, 92, 100.5), (100.5, 101, 100.2, 100.8)]
    b = bars_from(rows)  # ATR(1d)=3 -> max depth 4.5; swept to 90 -> acceptance
    ev, r, li = find_reclaim(b, 100.0, 0, "R1", cfg, 100)
    assert ev == "accept"


def test_calendar():
    assert cal.near_fomc(pd.Timestamp("2026-06-12", tz="UTC"), 7)
    assert not cal.near_fomc(pd.Timestamp("2026-06-01", tz="UTC"), 7)
    assert cal.days_to_quarter_close(pd.Timestamp("2026-06-30 12:00", tz="UTC")) == pytest.approx(0.5)
    assert cal.is_weekend(pd.Timestamp("2026-11-21", tz="UTC"))


def test_zone_merge_prefers_monthly_pivot():
    df = pd.DataFrame({
        "price": [100.0, 100.3, 120.0], "tf": ["W", "M", "W"], "kind": ["open_week", "pivot_low", "pivot_high"],
        "pivot_time": pd.to_datetime(["2025-01-01"] * 3, utc=True),
        "valid_from": pd.to_datetime(["2025-01-01"] * 3, utc=True), "valid_to": [pd.NaT] * 3, "prio": [14, 0, 10]})
    ls = LevelSet(df)
    z = ls.zone_of(100.0, ls.active(pd.Timestamp("2025-06-01", tz="UTC").value), 0.005)
    assert z["price"] == 100.3 and z["members"] == 2 and z["pivot_tf"] == "M"


def _trade(sym, side, t0, t1, risk_mult=1.0, stop_pct=0.08):
    return {"symbol": sym, "side": side, "entry_time": pd.Timestamp(t0, tz="UTC"),
            "exit_time": pd.Timestamp(t1, tz="UTC"), "risk_mult": risk_mult, "stop_pct": stop_pct, "lev_cap": 10.0,
            "weex_symbol": sym, "cluster": "crypto_alts", "R": 1.0, "mae_frac": 0.0, "fees_frac": 0.0,
            "base": sym[:-4], "entry": 1.0, "stop": 0.92, "tp2": 1.2, "outcome": "tp2", "exit_price": 1.2,
            "asset_class": "crypto", "tier": "T2", "level_tf": "W", "reclaim_variant": "R3w", "funding_frac": 0.0}


def test_portfolio_no_cluster_cap_open_risk_cap_one_per_side():
    from biss.portfolio import simulate as psim
    cfg = config.load()
    assert cfg.sizing.max_open_risk == pytest.approx(0.60) and cfg.sizing.get("max_per_cluster") is None
    eight = pd.DataFrame([_trade(f"C{i}USDT", "long", "2025-01-01", "2025-02-01") for i in range(8)])
    # 2% risk each: all 8 in one cluster are taken (the old cap was 3 per cluster)
    assert psim(eight, 0.02, cfg, {}, "a")["taken"] == 8
    # open-risk cap: 25% cap, 10% risk per trade -> 2 open
    res = psim(eight, 0.10, cfg.override(**{"sizing.max_open_risk": 0.25}), {}, "a")
    assert res["taken"] == 2 and res["skipped"]["open_risk_cap"] == 6
    # at 10% risk margin binds before the 60% cap: margin >= ~2.1x risk when liq sits 1 stop beyond the stop
    res = psim(eight, 0.10, cfg, {}, "a")
    assert res["taken"] == 5 and "open_risk_cap" not in res["skipped"]
    same = pd.DataFrame([_trade("C0USDT", "long", "2025-01-01", "2025-02-01"),
                         _trade("C0USDT", "short", "2025-01-02", "2025-02-01", 0.5),
                         _trade("C0USDT", "long", "2025-01-03", "2025-02-01")])
    res2 = psim(same, 0.02, cfg, {}, "a")
    # a long and a short on the same coin may both be open; a second long may not
    assert res2["taken"] == 2 and res2["skipped"]["same_symbol"] == 1


def test_scanner_profile_in_config():
    cfg = config.load()
    sc = cfg.scanner
    assert sc.reclaim == "R3w" and sc.entry == "E2" and sc.shorts and not sc.all_contracts
    assert list(sc.required_filters["long"]) == ["F2_drawdown", "F3_fomc", "F3_qclose", "F4_location", "stop_max"]
    assert list(sc.required_filters["short"]) == ["F3_fomc", "F3_qclose", "F4_location", "stop_max"]
    assert cfg.sweep.min_atr4h == pytest.approx(0.3) and cfg.sweep.skip_weekend and cfg.filters.fomc_days == 7
    assert cfg.sizing.default_risk == pytest.approx(0.10)
    caps = cfg.sizing.lev_caps
    assert all(caps[b] == 10 for b in cfg.universe.t1) and caps["crypto"] == 5
