"""24/7 PAPER scanner. Read-only market data; it never places orders and needs no API keys.

Each poll:
  1. daily bars (Binance fapi, same source as the backtest's levels) refreshed hourly;
  2. WEEX 15m bars (last ~30 days via historyKlines) for the sweep / reclaim / entry;
  3. setups.generate() on that window, the same code the backtest uses; filters and sizing as in analysis;
  4. alert new signals whose entry bar closed since the previous poll; track open paper trades to exit.

Run:  python -m biss.scanner.live            (loop)
      python -m biss.scanner.live --once     (single pass, for testing)
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from .. import calendar as cal
from .. import config
from ..analysis import FILTERS
from ..data import binance, weex
from ..indicators import btc_regime
from ..portfolio import cluster_of
from ..setups import generate
from ..sizing import lev_cap, mmr_for, size
from ..tiers import base_of
from ..universe import STABLE_OR_WRAPPED
from . import telegram

CHECKLIST = ("Manual checklist before acting: (1) Coinglass liquidation cluster at/under the level? "
             "(2) BTC context agrees? (3) isolated margin, leverage no higher than shown? "
             "(4) stop order placed at the stop, never widened?")


def _num(v):
    try:
        f = float(v)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def compact(s: dict) -> dict:
    """The fields of an enriched signal the dashboard and the state file keep."""
    z = s.get("size") or {}
    keep = ("symbol", "side", "tier", "level", "level_tf", "level_type", "pivot_tf", "swept_low", "entry", "stop",
            "stop_pct", "tp1_eff", "tp2", "rr_tp2", "risk_mult", "risk_pct", "conviction", "liq_price", "lev_cap",
            "passes", "risk_cap_ok", "sweep_depth_atr4h", "dd_from_120d", "days_to_fomc", "days_to_qclose")
    out = {k: (_num(s[k]) if isinstance(s.get(k), (int, float, np.floating, np.integer)) and not isinstance(s.get(k), bool)
               else s.get(k)) for k in keep}
    out["passes"], out["risk_cap_ok"] = bool(s.get("passes")), bool(s.get("risk_cap_ok"))
    for k in ("swept_time", "reclaim_time", "entry_time"):
        out[k] = str(s.get(k))
    out["filters"] = {k: bool(s[k]) for k in FILTERS if k in s}
    out["required"] = list(s.get("required") or [])
    out.update({"notional": _num(z.get("notional")), "margin": _num(z.get("margin")), "lev": _num(z.get("lev")),
                "risk_usd": _num(z.get("risk_usd"))})
    return out


class Scanner:
    def __init__(self, cfg):
        self.cfg = cfg
        self._recent: dict[str, list[dict]] = {}
        sc = cfg.scanner
        self.state_path = config.ROOT / sc.state_file
        self.state = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else \
            {"alerted": [], "open": [], "closed": []}
        self.daily: dict[str, pd.DataFrame] = {}
        self.daily_at = 0.0
        ei = weex.exchange_info()
        self.contracts = {s["symbol"]: s for s in ei["symbols"]}
        self.brackets = {x["symbol"]: x["brackets"] for x in weex.risk_limits()}
        self.symbols = self._symbols()

    def _symbols(self) -> list[str]:
        sc = self.cfg.scanner
        syms = list(sc.symbols)
        if sc.get("all_contracts"):
            return [s for s in self.contracts if s.isascii()
                    and (not sc.get("crypto_only") or self.contracts[s]["contractType"] == "PERPETUAL")]
        if sc.get("top_n_by_weex_volume"):
            tk = sorted(weex.ticker_24h(), key=lambda x: -float(x.get("quoteVolume") or 0))
            for x in tk:
                s = x["symbol"]
                c = self.contracts.get(s)
                if c and c["contractType"] == "PERPETUAL" and s not in syms and base_of(s) not in STABLE_OR_WRAPPED:
                    syms.append(s)
                if len(syms) >= sc.top_n_by_weex_volume:
                    break
        return [s for s in syms if s in self.contracts]

    def required(self, side: str) -> list[str]:
        rf = self.cfg.scanner.required_filters
        return list(rf[side]) if isinstance(rf, dict) else list(rf)

    def equity(self) -> float:
        """Paper equity = start + realised P&L of closed paper trades (gross of fees)."""
        return float(self.cfg.scanner.paper_equity) + sum(float(t.get("pnl_usd") or 0) for t in self.state["closed"])

    def open_risk_usd(self) -> float:
        """Risk still at stake: 0 once the stop is at entry (after the +1R partial)."""
        return sum(0.0 if t["half_done"] else float(t.get("risk_usd") or 0) for t in self.state["open"])

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")           # atomic: the dashboard reads this file
        tmp.write_text(json.dumps(self.state, default=str, indent=1), encoding="utf-8")
        tmp.replace(self.state_path)

    def refresh_daily(self) -> None:
        if time.time() - self.daily_at < 3600 and self.daily:
            return
        start = int(pd.Timestamp(self.cfg.data.warmup_start, tz="UTC").timestamp() * 1000)
        for s in self.symbols + ["BTCUSDT"]:
            try:
                d = binance.rest_klines(s, "1d", start)
            except Exception:  # noqa: BLE001
                d = pd.DataFrame()
            try:
                if d.empty:  # not on Binance: WEEX daily (<= 1000 bars)
                    d = weex.klines_recent(s, "1d", 1000)
                self.daily[s] = d
            except Exception as e:  # noqa: BLE001
                print("daily fail", s, e, flush=True)
        self.daily_at = time.time()

    def m15(self, sym: str, days: int = 30) -> pd.DataFrame:
        """WEEX 15m bars, cached: full 30-day backfill once, then only the latest bars each poll."""
        cache = getattr(self, "_m15", None)
        if cache is None:
            cache = self._m15 = {}
        now = pd.Timestamp.now(tz="UTC")
        df = cache.get(sym)
        if df is None or df.empty:
            end = int(time.time() * 1000) - 120_000
            df = weex.history_klines(sym, "15m", end - 30 * 86_400_000, end)
        else:
            new = weex.klines_recent(sym, "15m", 20)
            df = pd.concat([df, new])
            df = df[~df.index.duplicated(keep="last")].sort_index()
        df = df[df.index >= now - pd.Timedelta(days=35)]
        cache[sym] = df
        # drop the still-forming bar
        out = df[df.index + pd.Timedelta(minutes=15) <= now]
        return out[out.index >= now - pd.Timedelta(days=days)]

    def scan_symbol(self, sym: str, since: pd.Timestamp) -> list[dict]:
        cfg = self.cfg
        d, m = self.daily.get(sym), self.m15(sym)
        if d is None or d.empty or m.empty:
            return []
        d = d[d.index < m.index[-1].normalize() + pd.Timedelta(days=1)]
        sig = generate(sym, m, d, cfg, (m.index[0] + pd.Timedelta(days=3)).strftime("%Y-%m-%d"),
                       variants=(cfg.scanner.reclaim,), entries=(cfg.scanner.entry,),
                       sides=(1, -1) if cfg.scanner.shorts else (1,))
        if sig.empty:
            return []
        sig = sig[sig.skipped.fillna("") == ""]
        out = [self.enrich(sym, r.to_dict()) for _, r in sig.iterrows()]
        self._recent[sym] = [compact(s) for s in out]          # every setup in the 15m window, for the dashboard
        return [s for s in out if pd.Timestamp(s["entry_time"]) > since]

    def enrich(self, sym: str, s: dict) -> dict:
        cfg = self.cfg
        c = self.contracts[sym]
        asset = "crypto" if c["contractType"] == "PERPETUAL" else "tradfi"
        base = base_of(sym)
        btc = self.daily.get("BTCUSDT")
        bull = bool(btc_regime(btc, cfg.filters.regime_flip_days).iloc[-2]) if btc is not None else False
        f = cfg.filters
        lo, hi = (f.dd_crypto if asset == "crypto" else f.dd_tradfi)
        flags = {
            "F1_regime": (not bull) or asset != "crypto" or s["side"] == "short",
            "F1_bull": bull or asset != "crypto",          # short-side filter: BTC in its bull regime
            "F2_drawdown": bool(lo <= s["dd_from_120d"] <= hi),
            "F3_fomc": abs(s["days_to_fomc"]) > f.fomc_days,
            "F3_qclose": s["days_to_qclose"] > f.quarter_close_days,
            "F4_location": bool(s["f_location"]),
            "stop_max": bool(s["f_stop_ok"]),
            "min_rr": bool(s["f_rr_ok"]),
        }
        # conviction uses the backtest's F1 (analysis.enrich): BTC not in its bull regime, no exemption for shorts
        regime_ok = (not bull) or asset != "crypto"
        wk_ok = flags["F2_drawdown"] and (regime_ok if cfg.sizing.get("strong_needs_regime") else True)
        strong = s["pivot_tf"] == "M" or (s["pivot_tf"] == "W" and wk_ok)
        mult = cfg.sizing.tier_mult.strong if strong else cfg.sizing.tier_mult.weekly_only
        if s["side"] == "short":
            mult *= cfg.sizing.tier_mult.short
        if asset != "crypto":
            mult *= cfg.sizing.tier_mult.tradfi
        caps = dict(cfg.sizing.lev_caps)
        cap = lev_cap(base, "crypto" if asset == "crypto" else "stock", caps, c.get("maxLeverage"))
        eq = self.equity()
        free = eq - sum(float(t.get("margin") or 0) for t in self.state["open"])
        rp = float(cfg.sizing.default_risk) * mult
        z = size(eq, free, rp, s["stop_pct"], cap, self.brackets.get(sym), cfg.sizing.liq_buffer_mult,
                 bool(cfg.sizing.get("whole_leverage")))
        open_risk = self.open_risk_usd() / eq if eq > 0 else 1.0
        risk_cap_ok = open_risk + rp <= float(cfg.sizing.max_open_risk) + 1e-9
        sign = 1 if s["side"] == "long" else -1
        mmr = mmr_for(self.brackets.get(sym), z["notional"])[0]
        liq = s["entry"] * (1 - sign * (1 / z["lev"] - mmr)) if z["lev"] > 0 else float("nan")
        s.update(flags)
        req = self.required(s["side"])
        s.update({"symbol": sym, "asset_class": asset, "risk_mult": mult, "risk_pct": rp, "size": z, "liq_price": liq,
                  "weex_max_lev": c.get("maxLeverage"), "btc_bull": bull, "lev_cap": cap, "equity": eq,
                  "tier": "T1" if base in cfg.universe.t1 else "T2", "conviction": "strong" if strong else "weekly_only",
                  "open_risk_pct": open_risk, "risk_cap_ok": risk_cap_ok, "required": req,
                  "passes": all(flags[k] for k in req), "cluster": cluster_of(base, asset)})
        return s

    def message(self, s: dict) -> str:
        z = s["size"]
        dirw = "LONG" if s["side"] == "long" else "SHORT"
        fl = " ".join(f"{k}:{'ok' if s[k] else 'FAIL'}" for k in s["required"])
        info = " ".join(f"{k}:{'ok' if s[k] else 'no'}" for k in FILTERS if k not in s["required"])
        cap_line = (f"Open risk {100*s['open_risk_pct']:.1f}% + this {100*s['risk_pct']:.1f}% "
                    f"(cap {100*self.cfg.sizing.max_open_risk:.0f}%)"
                    + ("" if s["risk_cap_ok"] else " -> OVER CAP, not taken"))
        return (
            f"PAPER {dirw} {s['symbol']} ({s['tier']} {s['asset_class']})\n"
            f"HTF level {s['level']:g} [{s['level_type']}, TF {s['level_tf']}, {s['level_kinds']}, touches {s['touches']}]\n"
            f"Swept {'low' if s['side']=='long' else 'high'} {s['swept_low']:g} at {pd.Timestamp(s['swept_time']):%a %d %b %H:%M} UTC "
            f"(depth {100*s['sweep_depth_pct']:.2f}%, {s['sweep_depth_atr4h']:.2f} ATR4h)\n"
            f"Reclaim {pd.Timestamp(s['reclaim_time']):%d %b %H:%M} UTC on {s['reclaim_variant']} ({self.cfg.scanner.entry})\n"
            f"Entry ~{s['entry']:g} (range {s['entry']*(1-0.002):g}-{s['entry']*(1+0.002):g})\n"
            f"Stop {s['stop']:g} ({100*s['stop_pct']:.2f}%)  TP1 {s['tp1_eff']:g}  TP2 {s['tp2']:g}  R:R(TP2) {s['rr_tp2']:.2f}\n"
            f"Risk {s['conviction']} x{s['risk_mult']:.2f} -> {100*s['risk_pct']:.2f}% of ${s['equity']:,.0f} "
            f"(${z['risk_usd']:,.2f}): size ${z['notional']:,.0f}, margin ${z['margin']:,.0f} isolated, "
            f"lev {z['lev']:.1f}x (liq-safe max {z['need_lev']:.1f}x, cap {s['lev_cap']:g}x, WEEX max {s['weex_max_lev']}x)"
            f"{' - size cut to fit margin' if z['shrunk'] else ''}\n"
            f"{cap_line}\n"
            f"Liq price ~{s['liq_price']:g} vs stop {s['stop']:g}\n"
            f"Plan: 50% off at +1R ({s['entry'] + (1 if s['side']=='long' else -1)*abs(s['entry']-s['stop']):g}), stop to entry, rest to TP2.\n"
            f"Invalidation: 15m trade beyond {s['stop']:g}; no early exit on a close back through the level.\n"
            f"Required filters ({s['side']}): {fl}\n"
            f"Info only: {info} | BTC bull regime: {s['btc_bull']}\n"
            f"{CHECKLIST}"
        )

    def track(self) -> None:
        """Advance open paper trades with WEEX 15m bars (stop first on a bar that hits both)."""
        still = []
        for t in self.state["open"]:
            try:
                m = self.m15(t["symbol"], days=2)
            except Exception:  # noqa: BLE001
                still.append(t)
                continue
            m = m[m.index > pd.Timestamp(t["last_bar"])]
            sign = 1 if t["side"] == "long" else -1
            for ts, b in m.iterrows():
                lo, hi = (b.low, b.high) if sign > 0 else (-b.high, -b.low)
                stop, e = sign * t["stop"], sign * t["entry"]
                one_r = e + (e - sign * t["stop_orig"])
                tp2 = sign * t["tp2"]
                if lo <= stop:
                    t["legs"].append([str(ts), t["remaining"], t["stop"]])
                    t["remaining"] = 0
                    break
                if not t["half_done"] and hi >= one_r:
                    t["legs"].append([str(ts), 0.5, sign * one_r])
                    t["remaining"] = 0.5
                    t["half_done"] = True
                    t["stop"] = t["entry"]
                if hi >= tp2:
                    t["legs"].append([str(ts), t["remaining"], t["tp2"]])
                    t["remaining"] = 0
                    break
                t["last_bar"] = str(ts)
            if t["remaining"] <= 0:
                R = sum(q * sign * (px - t["entry"]) for _, q, px in t["legs"]) / abs(t["entry"] - t["stop_orig"])
                t["R_gross"] = R
                t["pnl_usd"] = R * float(t.get("risk_usd") or 0)
                self.state["closed"].append(t)
                telegram.send(f"PAPER CLOSED {t['side'].upper()} {t['symbol']}: {R:+.2f}R gross, "
                              f"${t['pnl_usd']:+,.2f} (paper equity ${self.equity():,.2f}) "
                              f"(entered {t['entry']:g}, legs {t['legs']})")
            else:
                still.append(t)
        self.state["open"] = still

    def poll(self) -> None:
        # only work when a new 15m bar has closed since the last scan
        bar = pd.Timestamp.now(tz="UTC").floor("15min")
        if self.state.get("last_bar_scanned") == str(bar):
            return
        self.state["last_bar_scanned"] = str(bar)
        self.refresh_daily()
        since = pd.Timestamp(self.state.get("last_poll") or (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=1)))
        now = pd.Timestamp.now(tz="UTC")
        t0, failed = time.time(), []
        alerts = self.state.setdefault("alerts", [])
        for sym in self.symbols:
            try:
                for s in self.scan_symbol(sym, since):
                    key = f"{sym}|{s['side']}|{s['level']:g}|{s['entry_time']}"
                    if key in self.state["alerted"]:
                        continue
                    self.state["alerted"].append(key)
                    if not s["passes"] and not self.cfg.scanner.alert_failed_filters:
                        continue
                    # one position per symbol and side, as in the backtest
                    if s["passes"] and any(o["symbol"] == sym and o["side"] == s["side"] for o in self.state["open"]):
                        continue
                    tag = "" if s["passes"] else "[FILTERS FAILED - info only]\n"
                    if s["passes"] and not s["risk_cap_ok"]:
                        tag = "[OPEN-RISK CAP - not taken]\n"
                    sent = telegram.send(tag + self.message(s))
                    alerts.append(compact(s) | {"alerted_at": str(now), "telegram": sent,
                                                "status": "taken" if s["passes"] and s["risk_cap_ok"] else
                                                ("over open-risk cap" if s["passes"] else "filters failed")})
                    del alerts[:-500]
                    if s["passes"] and s["risk_cap_ok"]:
                        self.state["open"].append({
                            "symbol": sym, "side": s["side"], "entry": s["entry"], "stop": s["stop"],
                            "stop_orig": s["stop"], "tp2": s["tp2"], "entry_time": str(s["entry_time"]),
                            "last_bar": str(pd.Timestamp(s["entry_time"]) - pd.Timedelta(minutes=15)),
                            "remaining": 1.0, "half_done": False, "legs": [],
                            "risk_usd": s["size"]["risk_usd"], "margin": s["size"]["margin"],
                            "lev": s["size"]["lev"], "risk_pct": s["risk_pct"], "tp1": s["tp1_eff"],
                            "level": s["level"], "tier": s["tier"], "conviction": s["conviction"],
                            "notional": s["size"]["notional"], "liq_price": s["liq_price"]})
            except Exception:  # noqa: BLE001
                failed.append(sym)
                print("scan fail", sym, traceback.format_exc()[-300:], flush=True)
        self.track()
        best: dict[tuple, dict] = {}            # one row per coin / side / entry (levels in one zone repeat)
        for x in (x for v in self._recent.values() for x in v):
            k = (x["symbol"], x["side"], x["entry_time"])
            if k not in best or (x["passes"] and not best[k]["passes"]):
                best[k] = x
        self.state["recent"] = sorted(best.values(), key=lambda x: (x["passes"], x["entry_time"]), reverse=True)[:300]
        self.state["health"] = {"symbols": len(self.symbols), "failed": failed[:50], "n_failed": len(failed),
                                "scan_seconds": round(time.time() - t0, 1), "bar": str(bar),
                                "open_risk_pct": self.open_risk_usd() / self.equity() if self.equity() > 0 else None}
        self.state["last_poll"] = str(now)
        self.save()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    cfg = config.load(a.config)
    sc = Scanner(cfg)
    print(f"paper scanner: {len(sc.symbols)} symbols, reclaim {cfg.scanner.reclaim}/{cfg.scanner.entry}, "
          f"shorts {cfg.scanner.shorts}, risk {cfg.sizing.default_risk:.0%} base, open-risk cap "
          f"{cfg.sizing.max_open_risk:.0%}, paper equity ${sc.equity():,.2f}, "
          f"telegram {'on' if telegram.configured() else 'OFF (printing)'}", flush=True)
    if a.once:
        sc.poll()
        return
    while True:
        t0 = time.time()
        try:
            sc.poll()
        except Exception:  # noqa: BLE001
            print("poll fail", traceback.format_exc()[-500:], flush=True)
        time.sleep(max(5.0, cfg.scanner.poll_seconds - (time.time() - t0)))


if __name__ == "__main__":
    main()
