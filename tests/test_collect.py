"""Research collector: outcome tracker, order-book stats, the database schema."""
from __future__ import annotations

import pytest

from biss.collect import db, tracker
from biss.collect.collector import book_stats, setup_key

M = 15 * 60_000
T0 = 1_790_000_000_000 - (1_790_000_000_000 % M)


def bars(rows, t0=T0):
    """rows of (high, low, close) -> (t, o, h, l, c)"""
    return [(t0 + i * M, c, h, lo, c) for i, (h, lo, c) in enumerate(rows)]


def test_long_partial_then_breakeven_and_hits():
    st = tracker.new_state(100.0, 95.0, tp1=110.0, tp2=120.0, level=98.0, side="long", entry_time_ms=T0)
    tracker.advance(st, bars([(103, 99, 102), (106, 101, 105), (106, 99.5, 100), (101, 97, 97.5)]))
    p = st["exits"]["partial_1r_be"]
    assert not p["open"] and p["r"] == pytest.approx(0.5)          # half at +1R, rest stopped at entry
    assert st["hits"]["+1R"] == T0 + M and "tp2" not in st["hits"] and st["hits"]["close_back"] == T0 + 3 * M
    assert st["exits"]["fixed_2r"]["open"] and st["mfe"] == pytest.approx(1.2) and st["mae"] == pytest.approx(-0.6)


def test_short_mirrored_target_and_stop_first():
    st = tracker.new_state(100.0, 105.0, tp1=90.0, tp2=80.0, level=102.0, side="short", entry_time_ms=T0)
    tracker.advance(st, bars([(101, 94, 95), (96, 79, 80)]))
    p = st["exits"]["partial_1r_be"]
    assert p["r"] == pytest.approx(0.5 + 0.5 * 4.0)                  # +1R half, rest at TP2 (+4R)
    assert st["exits"]["fixed_2r"]["r"] == 2.0 and st["exits"]["tp2"]["r"] == pytest.approx(4.0)
    st2 = tracker.new_state(100.0, 95.0, tp1=110.0, tp2=120.0, level=98.0, side="long", entry_time_ms=T0)
    tracker.advance(st2, bars([(106, 94, 100)]))                       # both -1R and +1R in one bar: stop first
    assert st2["exits"]["partial_1r_be"]["r"] == -1.0 and st2["ambiguous"] == 1


def test_incremental_equals_one_pass_and_done_after_30_days():
    rows = [(100 + (i % 7), 99 - (i % 5) * 0.3, 100 + (i % 3)) for i in range(40)]
    a = tracker.new_state(100.0, 95.0, 110.0, 130.0, 98.0, "long", T0)
    b = tracker.new_state(100.0, 95.0, 110.0, 130.0, 98.0, "long", T0)
    tracker.advance(a, bars(rows))
    tracker.advance(b, bars(rows[:15]))
    tracker.advance(b, bars(rows))                                     # re-fed bars are ignored
    assert tracker.summary(a) == tracker.summary(b)
    late = tracker.new_state(100.0, 95.0, 110.0, 130.0, 98.0, "long", T0)
    tracker.advance(late, bars([(101, 99, 100.5)]) + [(T0 + 31 * tracker.DAY_MS, 100, 101, 99, 100)])
    assert late["done"] and late["exits"]["fixed_3r"].get("marked")


def test_book_stats_and_keys(tmp_path):
    s = book_stats({"bids": [["99.9", "10"], ["99.0", "100"]], "asks": [["100.1", "10"], ["101.5", "50"]]})
    assert s["mid"] == pytest.approx(100.0) and s["spread_bps"] == pytest.approx(20.0)
    assert s["bid_usd_05"] == pytest.approx(999.0) and s["bid_usd_1"] == pytest.approx(999 + 9900)
    assert s["ask_usd_2"] == pytest.approx(1001 + 5075)
    k = setup_key({"symbol": "ETHUSDT", "side": "long", "level": 2950.0, "entry_time": "2026-11-23 01:15:00+00:00",
                   "reclaim_variant": "R3w", "entry_variant": "E2"})
    assert k.startswith("ETHUSDT|long|2950|") and k.endswith("|R3w|E2")
    conn = db.connect(tmp_path / "x.sqlite")
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(db.TABLES) <= names
