"""Collects research data beside the paper scanner. It only records; it never changes alerts or paper trades.

  after_poll()  scanner thread, once per scan: WEEX 15m/daily bars, every setup (passing, failing, skipped),
                setup outcome tracking, WEEX ticker + funding snapshot, universe ranks (daily), scan row
  hourly thread: Binance open interest / long-short ratios / taker flow / funding, WEEX open interest and
                order-book depth for every scanned symbol
  liquidation thread: Binance all-market liquidation stream (websocket), scanned symbols + BTC/ETH
Every step is wrapped: a collector error is logged to the events table and never stops the scanner.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
import traceback

import pandas as pd

from .. import config
from ..data import binance, weex
from ..indicators import btc_regime
from ..tiers import base_of
from ..universe import STABLE_OR_WRAPPED
from . import db, tracker

M15 = 15 * 60_000
# Binance serves market streams under /market/ws/ (the old /ws/ URL still connects but stays silent)
LIQ_WS = "wss://fstream.binance.com/market/ws/!forceOrder@arr"


def config_hash(cfg) -> str:
    keep = {k: cfg.get(k) for k in ("scanner", "sizing", "filters", "sweep", "stop", "targets", "levels", "reclaim",
                                    "entry", "universe")}
    return hashlib.sha1(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:10]


def setup_key(s: dict) -> str:
    t = s.get("entry_time")
    if t is None or str(t) in ("NaT", "None", "nan"):
        t = s.get("swept_time")
    return f"{s['symbol']}|{s['side']}|{float(s['level']):.10g}|{db.ms(t)}|{s.get('reclaim_variant')}|{s.get('entry_variant')}"


def book_stats(book: dict) -> dict | None:
    bids = [(float(p), float(q)) for p, q in book.get("bids", [])]
    asks = [(float(p), float(q)) for p, q in book.get("asks", [])]
    if not bids or not asks:
        return None
    bb, ba = bids[0][0], asks[0][0]
    mid = (bb + ba) / 2
    out = {"mid": mid, "spread_bps": (ba - bb) / mid * 1e4, "levels": min(len(bids), len(asks))}
    for pct, name in ((0.005, "05"), (0.01, "1"), (0.02, "2")):
        out[f"bid_usd_{name}"] = sum(p * q for p, q in bids if p >= mid * (1 - pct))
        out[f"ask_usd_{name}"] = sum(p * q for p, q in asks if p <= mid * (1 + pct))
    return out


class Collector:
    def __init__(self, cfg):
        self.cfg = cfg
        cc = cfg.get("collect") or {}
        self.path = config.ROOT / cc.get("db_path", "data/biss.sqlite")
        self.hourly_min = float(cc.get("hourly_minutes", 60))
        self.want_liq = bool(cc.get("liquidations", True))
        self.conn = db.connect(self.path)
        self.version = os.environ.get("APP_VERSION", "dev")[:7]
        self.chash = config_hash(cfg)
        self.saved_15m: dict[str, int] = {}
        self.daily_saved_at = 0.0
        self.tracks: dict[str, dict] = {}
        self.universe_day = ""
        self.scanner = None
        self.liq_symbols: set[str] = set()
        self._load_tracks()
        self.conn.execute("INSERT OR REPLACE INTO meta VALUES('config_hash', ?)", (self.chash,))
        self.conn.commit()

    # ---- helpers -----------------------------------------------------------------------------
    def _err(self, where: str, conn=None) -> None:
        msg = traceback.format_exc()[-800:]
        print("collector error", where, msg[-300:], flush=True)
        try:
            c = conn or self.conn
            c.execute("INSERT INTO events VALUES(?,?,?,?)", (int(time.time() * 1000), "collect_error", where, msg))
            c.commit()
        except Exception:  # noqa: BLE001
            pass

    def event(self, kind: str, symbol: str | None, detail) -> None:
        try:
            self.conn.execute("INSERT INTO events VALUES(?,?,?,?)",
                              (int(time.time() * 1000), kind, symbol, db.to_json(detail)))
            self.conn.commit()
        except Exception:  # noqa: BLE001
            self._err("event")

    def _load_tracks(self) -> None:
        for r in self.conn.execute("SELECT key, state FROM setup_tracks WHERE done=0"):
            try:
                self.tracks[r["key"]] = json.loads(r["state"])
            except ValueError:
                pass

    # ---- once per scan -----------------------------------------------------------------------
    def after_poll(self, sc, now: pd.Timestamp, bar: pd.Timestamp, seconds: float, failed: list[str]) -> None:
        self.scanner = sc
        self.liq_symbols = set(sc.symbols) | {"BTCUSDT", "ETHUSDT"}
        n_setups = n_new = 0
        for name, fn in (("bars", lambda: self._bars(sc, now)), ("daily", lambda: self._daily(sc)),
                         ("tracks", lambda: self._tracks(sc, now)), ("market", lambda: self._market(sc, now)),
                         ("universe", lambda: self._universe(sc, now))):
            if name == "tracks":
                try:
                    n_setups, n_new = self._setups(sc, now)
                except Exception:  # noqa: BLE001
                    self._err("setups")
            try:
                fn()
            except Exception:  # noqa: BLE001
                self._err(name)
        try:
            self._scan_row(sc, now, bar, seconds, failed, n_setups, n_new)
        except Exception:  # noqa: BLE001
            self._err("scan_row")
        self.conn.commit()

    def _closed(self, df: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
        return df[df.index + pd.Timedelta(minutes=15) <= now]

    def _bars(self, sc, now) -> None:
        cache = getattr(sc, "_m15", {}) or {}
        rows = []
        for sym, df in cache.items():
            if df is None or df.empty:
                continue
            d = self._closed(df, now)
            t = d.index.as_unit("ns").asi8 // 1_000_000
            last = self.saved_15m.get(sym)
            if last is None:
                r = self.conn.execute("SELECT MAX(t) FROM bars_15m WHERE symbol=?", (sym,)).fetchone()[0]
                last = int(r) if r is not None else -1
            m = t > last
            if not m.any():
                continue
            qv = d["quote_volume"] if "quote_volume" in d else pd.Series(float("nan"), index=d.index)
            for ti, o, h, lo, c, v, q in zip(t[m], d.open[m], d.high[m], d.low[m], d.close[m], d.volume[m], qv[m]):
                rows.append((sym, int(ti), db.num(o), db.num(h), db.num(lo), db.num(c), db.num(v), db.num(q)))
            self.saved_15m[sym] = int(t[m].max())
        if rows:
            self.conn.executemany("INSERT OR IGNORE INTO bars_15m VALUES(?,?,?,?,?,?,?,?)", rows)

    def _daily(self, sc) -> None:
        if getattr(sc, "daily_at", 0) == self.daily_saved_at:
            return
        rows = []
        first = self.daily_saved_at == 0
        for sym, df in (sc.daily or {}).items():
            if df is None or df.empty:
                continue
            d = df if first else df.tail(5)
            t = d.index.as_unit("ns").asi8 // 1_000_000
            qv = d["quote_volume"] if "quote_volume" in d else pd.Series(float("nan"), index=d.index)
            for ti, o, h, lo, c, v, q in zip(t, d.open, d.high, d.low, d.close, d.volume, qv):
                rows.append((sym, int(ti), db.num(o), db.num(h), db.num(lo), db.num(c), db.num(v), db.num(q), "scanner"))
        self.conn.executemany("INSERT OR REPLACE INTO bars_1d VALUES(?,?,?,?,?,?,?,?,?)", rows)
        self.daily_saved_at = sc.daily_at

    def _setups(self, sc, now) -> tuple[int, int]:
        now_ms = db.ms(now)
        started = getattr(sc, "started_ms", now_ms)
        n = new = 0
        for sym, sigs in (getattr(sc, "_full", {}) or {}).items():
            for s in sigs:
                n += 1
                new += self._upsert_setup(s, now_ms, started, skipped=False)
        for sym, sigs in (getattr(sc, "_skipped", {}) or {}).items():
            for s in sigs:
                n += 1
                new += self._upsert_setup(s, now_ms, started, skipped=True)
        return n, new

    def _upsert_setup(self, s: dict, now_ms: int, started: int, skipped: bool) -> int:
        key = setup_key(s)
        cur = self.conn.execute("SELECT 1 FROM setups WHERE key=?", (key,)).fetchone()
        if cur:
            self.conn.execute("UPDATE setups SET last_seen=? WHERE key=?", (now_ms, key))
            return 0
        z = s.get("size") or {}
        req = list(s.get("required") or [])
        failed = [k for k in req if not s.get(k)]
        et = db.ms(s.get("entry_time"))
        live = int(et is not None and et >= started)
        self.conn.execute(
            "INSERT INTO setups(key,symbol,side,tier,reclaim,entry_variant,attempt,level,level_tf,pivot_tf,level_type,"
            "swept_time,reclaim_time,entry_time,entry,stop,stop_pct,tp1,tp2,rr_tp2,passes,failed,skipped,risk_mult,"
            "risk_pct,lev,btc_bull,live,first_seen,last_seen,app_version,config_hash,features) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, s["symbol"], s["side"], s.get("tier"), s.get("reclaim_variant"), s.get("entry_variant"),
             s.get("attempt"), db.num(s.get("level")), s.get("level_tf"), s.get("pivot_tf"), s.get("level_type"),
             db.ms(s.get("swept_time")), db.ms(s.get("reclaim_time")), et, db.num(s.get("entry")),
             db.num(s.get("stop")), db.num(s.get("stop_pct")), db.num(s.get("tp1_eff")), db.num(s.get("tp2")),
             db.num(s.get("rr_tp2")), None if skipped else int(bool(s.get("passes"))), ",".join(failed),
             s.get("skipped") or "", db.num(s.get("risk_mult")), db.num(s.get("risk_pct")), db.num(z.get("lev")),
             None if s.get("btc_bull") is None else int(bool(s.get("btc_bull"))), live, now_ms, now_ms,
             self.version, self.chash, db.to_json({k: v for k, v in s.items() if k != "size"} | {"size": z})))
        if not skipped and et is not None and s.get("stop") and s.get("entry"):
            st = tracker.new_state(float(s["entry"]), float(s["stop"]), db.num(s.get("tp1_eff")), db.num(s.get("tp2")),
                                   float(s["level"]), s["side"], et)
            self.tracks[key] = st
            self.conn.execute("INSERT OR REPLACE INTO setup_tracks(key,symbol,last_bar,done,updated,state) "
                              "VALUES(?,?,?,?,?,?)", (key, s["symbol"], st["last_bar"], 0, now_ms, db.to_json(st)))
            if live:
                self._book_async(s["symbol"], "setup")
        return 1

    def _tracks(self, sc, now) -> None:
        cache = getattr(sc, "_m15", {}) or {}
        now_ms = db.ms(now)
        done = []
        for key, st in self.tracks.items():
            sym = key.split("|", 1)[0]
            df = cache.get(sym)
            if df is not None and not df.empty:
                d = self._closed(df, now)
                t = d.index.as_unit("ns").asi8 // 1_000_000
                m = t > st["last_bar"]
                if m.any():
                    tracker.advance(st, zip(t[m], d.open[m], d.high[m], d.low[m], d.close[m]))
            if now_ms - st["t0"] > (tracker.TRACK_DAYS + 1) * tracker.DAY_MS and not st["done"]:
                st["done"] = True                    # bars no longer available: close at what we have
                tracker.advance(st, [])
            sm = tracker.summary(st)
            self.conn.execute(
                "UPDATE setup_tracks SET last_bar=?, done=?, updated=?, r_partial_be=?, r_fixed_2r=?, r_fixed_3r=?, "
                "r_tp1=?, r_tp2=?, mfe_r=?, mae_r=?, state=? WHERE key=?",
                (st["last_bar"], int(st["done"]), now_ms, sm["r_partial_be"], sm["r_fixed_2r"], sm["r_fixed_3r"],
                 sm["r_tp1"], sm["r_tp2"], sm["mfe_r"], sm["mae_r"], db.to_json(st), key))
            if st["done"]:
                done.append(key)
        for k in done:
            self.tracks.pop(k, None)

    def _market(self, sc, now) -> None:
        want = set(sc.symbols) | {"BTCUSDT", "ETHUSDT"}
        tk = {x["symbol"]: x for x in weex.ticker_24h() if x.get("symbol") in want}
        pi = {x["symbol"]: x for x in weex.premium_index() if x.get("symbol") in want}
        ts = db.ms(now)
        rows = []
        for s in want:
            a, b = tk.get(s, {}), pi.get(s, {})
            if not a and not b:
                continue
            rows.append((ts, s, db.num(a.get("lastPrice")), db.num(b.get("markPrice") or a.get("markPrice")),
                         db.num(b.get("indexPrice") or a.get("indexPrice")), db.num(b.get("lastFundingRate")),
                         db.num(b.get("forecastFundingRate")), db.num(a.get("quoteVolume")),
                         db.num(a.get("priceChangePercent"))))
        self.conn.executemany("INSERT OR IGNORE INTO market_snap VALUES(?,?,?,?,?,?,?,?,?)", rows)
        self._ticker = tk

    def _universe(self, sc, now) -> None:
        day = now.strftime("%Y-%m-%d")
        if day == self.universe_day:
            return
        if self.conn.execute("SELECT 1 FROM universe_snap WHERE day=? LIMIT 1", (day,)).fetchone():
            self.universe_day = day
            return
        tk = sorted(weex.ticker_24h(), key=lambda x: -float(x.get("quoteVolume") or 0))
        rows, rank = [], 0
        for x in tk:
            s = x.get("symbol", "")
            c = sc.contracts.get(s)
            if not c or c.get("contractType") != "PERPETUAL" or base_of(s) in STABLE_OR_WRAPPED or not s.isascii():
                continue
            rank += 1
            rows.append((day, s, rank, db.num(x.get("quoteVolume")), int(s in sc.symbols)))
            if rank >= 150:
                break
        self.conn.executemany("INSERT OR IGNORE INTO universe_snap VALUES(?,?,?,?,?)", rows)
        self.universe_day = day

    def _scan_row(self, sc, now, bar, seconds, failed, n_setups, n_new) -> None:
        btc = (sc.daily or {}).get("BTCUSDT")
        close = s50 = s200 = bull = bear = None
        if btc is not None and len(btc) > 210:
            c = btc["close"]
            close, s50, s200 = float(c.iloc[-2]), float(c.rolling(50).mean().iloc[-2]), float(c.rolling(200).mean().iloc[-2])
            n = self.cfg.filters.regime_flip_days
            bull = int(bool(btc_regime(btc, n).iloc[-2]))
            bear = int(bool(btc_regime(btc, n, bear=True).iloc[-2]))
        self.conn.execute("INSERT OR REPLACE INTO scans VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (db.ms(now), db.ms(bar), len(sc.symbols), len(failed), seconds, n_setups, n_new, close, s50,
                           s200, bull, bear, self.version))

    # ---- order book (own thread, own connection) ------------------------------------------------
    def _book_async(self, symbol: str, reason: str) -> None:
        threading.Thread(target=self._book_one, args=(symbol, reason), daemon=True).start()

    def _book_one(self, symbol: str, reason: str, conn=None) -> None:
        own = conn is None
        try:
            conn = conn or db.connect(self.path)
            st = book_stats(weex.depth(symbol, 200))
            if st:
                conn.execute("INSERT OR IGNORE INTO book_snap VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                             (int(time.time() * 1000), symbol, reason, st["mid"], st["spread_bps"], st["bid_usd_05"],
                              st["ask_usd_05"], st["bid_usd_1"], st["ask_usd_1"], st["bid_usd_2"], st["ask_usd_2"],
                              st["levels"]))
                conn.commit()
        except Exception:  # noqa: BLE001
            self._err(f"book {symbol}", conn if conn is not None else None)
        finally:
            if own and conn is not None:
                conn.close()

    # ---- hourly derivatives + books ----------------------------------------------------------------
    def _hourly_once(self, conn) -> None:
        sc = self.scanner
        if sc is None:
            return
        ts = int(time.time() * 1000)
        syms = list(dict.fromkeys(list(sc.symbols) + ["BTCUSDT", "ETHUSDT"]))
        try:
            r = binance._get(f"{binance.FAPI}/fapi/v1/premiumIndex")
            bpi = {x["symbol"]: x for x in (r.json() if r is not None else [])}
        except Exception:  # noqa: BLE001
            bpi = {}
        rows = []
        for s in syms:
            try:
                def one(path, **p):
                    resp = binance._get(f"{binance.FAPI}/{path}", {"symbol": s, "period": "1h", "limit": 1, **p})
                    d = resp.json() if resp is not None else None
                    return d[-1] if isinstance(d, list) and d else {}
                oi = one("futures/data/openInterestHist") if s in bpi else {}
                gl = one("futures/data/globalLongShortAccountRatio") if s in bpi else {}
                tp = one("futures/data/topLongShortPositionRatio") if s in bpi else {}
                tk = one("futures/data/takerlongshortRatio") if s in bpi else {}
                try:
                    woi = db.num(weex.open_interest(s).get("openInterest"))
                except Exception:  # noqa: BLE001
                    woi = None
                b = bpi.get(s, {})
                rows.append((ts, s, woi, db.num(oi.get("sumOpenInterest")), db.num(oi.get("sumOpenInterestValue")),
                             db.num(b.get("lastFundingRate")), db.num(b.get("markPrice")),
                             db.num(gl.get("longShortRatio")), db.num(tp.get("longShortRatio")),
                             db.num(tk.get("buySellRatio"))))
            except Exception:  # noqa: BLE001
                self._err(f"deriv {s}", conn)
            self._book_one(s, "hourly", conn)
            time.sleep(0.2)
        conn.executemany("INSERT OR IGNORE INTO deriv_snap VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()

    def _hourly_loop(self) -> None:
        conn = db.connect(self.path)
        while self.scanner is None:                 # wait for the first scan (it sets the symbol list)
            time.sleep(60)
        while True:
            t0 = time.time()
            try:
                self._hourly_once(conn)
            except Exception:  # noqa: BLE001
                self._err("hourly", conn)
            time.sleep(max(60.0, self.hourly_min * 60 - (time.time() - t0)))

    # ---- liquidations (websocket) -----------------------------------------------------------------
    async def _liq_ws(self) -> None:
        import aiohttp
        conn = db.connect(self.path)
        buf: list[tuple] = []
        last_flush = time.time()
        backoff = 5
        while True:
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.ws_connect(LIQ_WS, heartbeat=60, timeout=30) as ws:
                        backoff = 5
                        last_msg = time.time()
                        while True:
                            try:
                                msg = await ws.receive(timeout=15)
                            except asyncio.TimeoutError:
                                msg = None
                            if msg is not None:
                                if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING,
                                                aiohttp.WSMsgType.ERROR):
                                    break
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    last_msg = time.time()
                                    o = (json.loads(msg.data) or {}).get("o") or {}
                                    sym = o.get("s")
                                    if sym in self.liq_symbols or not self.liq_symbols:
                                        px, q = db.num(o.get("ap") or o.get("p")), db.num(o.get("z") or o.get("q"))
                                        side = "long_liq" if o.get("S") == "SELL" else "short_liq"
                                        buf.append((int(o.get("T") or time.time() * 1000), sym, side, px, q,
                                                    (px or 0) * (q or 0)))
                            if buf and time.time() - last_flush > 10:
                                conn.executemany("INSERT INTO liquidations VALUES(?,?,?,?,?,?)", buf)
                                conn.commit()
                                buf, last_flush = [], time.time()
                            if time.time() - last_msg > 1800:     # silent for 30 min: reconnect
                                break
            except Exception:  # noqa: BLE001
                self._err("liquidations", conn)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)

    def start_background(self) -> None:
        threading.Thread(target=self._hourly_loop, name="collect-hourly", daemon=True).start()
        if self.want_liq:
            threading.Thread(target=lambda: asyncio.run(self._liq_ws()), name="collect-liq", daemon=True).start()
