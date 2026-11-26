"""SQLite store for the research data (WAL mode: the scanner, the background collectors and the read-only
dashboard each use their own connection). Times are UTC epoch milliseconds unless a column says otherwise.
"""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);

-- every setup the scanner computes (passing or not, plus skipped ones), first seen / last seen
CREATE TABLE IF NOT EXISTS setups(
  key TEXT PRIMARY KEY, symbol TEXT, side TEXT, tier TEXT, reclaim TEXT, entry_variant TEXT, attempt INT,
  level REAL, level_tf TEXT, pivot_tf TEXT, level_type TEXT, swept_time INT, reclaim_time INT, entry_time INT,
  entry REAL, stop REAL, stop_pct REAL, tp1 REAL, tp2 REAL, rr_tp2 REAL,
  passes INT, failed TEXT, skipped TEXT, risk_mult REAL, risk_pct REAL, lev REAL, btc_bull INT,
  live INT,                       -- 1 = entry after the scanner started (alertable), 0 = found in the backfill window
  first_seen INT, last_seen INT, alerted INT DEFAULT 0, alert_status TEXT,
  app_version TEXT, config_hash TEXT, features TEXT);
CREATE INDEX IF NOT EXISTS setups_entry ON setups(entry_time);

-- forward path of every setup on WEEX 15m bars (gross R, no fees), updated each scan for 30 days
CREATE TABLE IF NOT EXISTS setup_tracks(
  key TEXT PRIMARY KEY, symbol TEXT, last_bar INT, done INT, updated INT,
  r_partial_be REAL, r_fixed_2r REAL, r_fixed_3r REAL, r_tp1 REAL, r_tp2 REAL, mfe_r REAL, mae_r REAL, state TEXT);

-- raw WEEX bars (what the scanner saw), so any rule can be replayed later
CREATE TABLE IF NOT EXISTS bars_15m(symbol TEXT, t INT, o REAL, h REAL, l REAL, c REAL, v REAL, qv REAL,
  PRIMARY KEY(symbol, t)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS bars_1d(symbol TEXT, t INT, o REAL, h REAL, l REAL, c REAL, v REAL, qv REAL, source TEXT,
  PRIMARY KEY(symbol, t)) WITHOUT ROWID;

-- every scan (15m): WEEX ticker + premium index for the scanned symbols
CREATE TABLE IF NOT EXISTS market_snap(ts INT, symbol TEXT, last REAL, mark REAL, idx REAL, funding_last REAL,
  funding_next REAL, qv24 REAL, chg24 REAL, PRIMARY KEY(ts, symbol)) WITHOUT ROWID;

-- hourly derivatives context (Binance futures data + WEEX open interest)
CREATE TABLE IF NOT EXISTS deriv_snap(ts INT, symbol TEXT, weex_oi REAL, bn_oi REAL, bn_oi_usd REAL,
  bn_funding REAL, bn_mark REAL, ls_global REAL, ls_top_pos REAL, taker_buy_sell REAL,
  PRIMARY KEY(ts, symbol)) WITHOUT ROWID;

-- WEEX order book: hourly for every scanned symbol, and when a setup / alert appears (reason)
CREATE TABLE IF NOT EXISTS book_snap(ts INT, symbol TEXT, reason TEXT, mid REAL, spread_bps REAL,
  bid_usd_05 REAL, ask_usd_05 REAL, bid_usd_1 REAL, ask_usd_1 REAL, bid_usd_2 REAL, ask_usd_2 REAL, levels INT,
  PRIMARY KEY(ts, symbol, reason)) WITHOUT ROWID;

-- Binance all-market liquidation stream (largest order per symbol per second), scanned symbols + BTC/ETH
CREATE TABLE IF NOT EXISTS liquidations(ts INT, symbol TEXT, side TEXT, price REAL, qty REAL, usd REAL);
CREATE INDEX IF NOT EXISTS liq_sym_ts ON liquidations(symbol, ts);

-- daily: the WEEX crypto perps ranked by 24h volume (how the T2 universe drifts) and whether scanned
CREATE TABLE IF NOT EXISTS universe_snap(day TEXT, symbol TEXT, rank INT, qv24 REAL, scanned INT,
  PRIMARY KEY(day, symbol)) WITHOUT ROWID;

-- one row per scan: health and BTC regime inputs
CREATE TABLE IF NOT EXISTS scans(ts INT PRIMARY KEY, bar INT, n_symbols INT, n_failed INT, seconds REAL,
  n_setups INT, n_new INT, btc_close REAL, btc_sma50 REAL, btc_sma200 REAL, btc_bull INT, btc_bear INT,
  app_version TEXT);

-- alerts, paper trade opens / closes, starts, collector errors
CREATE TABLE IF NOT EXISTS events(ts INT, kind TEXT, symbol TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS events_ts ON events(ts);
"""

TABLES = ("setups", "setup_tracks", "bars_15m", "bars_1d", "market_snap", "deriv_snap", "book_snap",
          "liquidations", "universe_snap", "scans", "events")


def connect(path: Path, readonly: bool = False) -> sqlite3.Connection:
    path = Path(path)
    if readonly:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=30)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(SCHEMA)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    return conn


def ms(t) -> int | None:
    """Timestamp-ish -> epoch ms."""
    if t is None or (isinstance(t, float) and math.isnan(t)):
        return None
    try:
        ts = pd.Timestamp(t)
    except (ValueError, TypeError):
        return None
    if ts is pd.NaT:
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return int(ts.value // 1_000_000)


def _plain(v):
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        f = float(v)
        return f if math.isfinite(f) else None
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, (pd.Timestamp,)):
        return None if v is pd.NaT else v.isoformat()
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


def to_json(d) -> str:
    return json.dumps(_plain(d), default=str, separators=(",", ":"))


def num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None
