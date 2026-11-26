"""Dashboard: login gate, snapshot from the scanner state, backtest export."""
from __future__ import annotations

import asyncio
import json

from aiohttp.test_utils import TestClient, TestServer

from biss import config, dashboard


def _cfg(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({
        "open": [{"symbol": "ETHUSDT", "side": "long", "entry": 3000, "stop": 2880, "stop_orig": 2880, "tp2": 3400,
                  "half_done": False, "risk_usd": 100.0, "margin": 250.0, "legs": []}],
        "closed": [{"symbol": "SOLUSDT", "side": "short", "R_gross": 2.0, "pnl_usd": 60.0, "legs": []}],
        "alerts": [], "recent": [], "health": {"symbols": 50}, "last_poll": "2026-11-26 16:30:00+00:00"}),
        encoding="utf-8")
    return config.load().override(**{"scanner.state_file": str(state), "data.dir": str(tmp_path)})


def test_snapshot_reads_state(tmp_path):
    d = dashboard.snapshot(_cfg(tmp_path))
    assert d["equity"] == 1060.0 and len(d["open"]) == 1 and d["paper_stats"]["avg_r"] == 2.0
    assert d["profile"]["reclaim"] == "R3w" and d["profile"]["max_open_risk"] == 0.6


def test_login_required_and_backtest_served(tmp_path):
    async def run():
        app = dashboard.build_app(_cfg(tmp_path), "s3cret-pass", need_login=True, cookie_secure=False)
        async with TestClient(TestServer(app)) as c:
            assert (await c.get("/")).status == 200                     # page itself is public (login form)
            assert (await c.get("/api/data")).status == 401
            assert (await c.post("/login", json={"password": "wrong"})).status == 401
            assert (await c.post("/login", json={"password": "s3cret-pass"})).status == 200
            r = await c.get("/api/data")
            assert r.status == 200 and (await r.json())["equity"] == 1060.0
            b = await c.get("/api/backtest")
            if dashboard.BACKTEST.exists():
                bt = await b.json()
                assert bt["summary"]["signals"] > 0 and len(bt["trades"]) == bt["summary"]["route_taken"]
    asyncio.run(run())


def test_scanner_conviction_needs_btc_regime(monkeypatch):
    import pandas as pd
    from biss.scanner import live
    cfg = config.load()
    assert cfg.sizing.strong_needs_regime
    s = live.Scanner.__new__(live.Scanner)
    s.cfg, s.brackets, s._recent = cfg, {}, {}
    s.state = {"alerted": [], "open": [], "closed": []}
    s.contracts = {"DOGEUSDT": {"contractType": "PERPETUAL", "maxLeverage": 50}}
    sig = dict(side="long", pivot_tf="W", dd_from_120d=0.35, days_to_fomc=-20, days_to_qclose=30, f_location=True,
               f_stop_ok=True, f_rr_ok=True, stop_pct=0.05, entry=1.0)
    for bull, mult in ((False, 1.0), (True, 0.6)):
        s.daily = {"BTCUSDT": pd.DataFrame({"close": [1.0, 1.0]})}
        monkeypatch.setattr(live, "btc_regime", lambda d, n, b=bull: pd.Series([b, b]))
        assert s.enrich("DOGEUSDT", dict(sig))["risk_mult"] == mult
    short = s.enrich("DOGEUSDT", dict(sig, side="short"))       # bull regime: weekly short is 0.6 x 0.5
    assert short["risk_mult"] == 0.3 and short["passes"]            # shorts need BTC in its bull regime
    monkeypatch.setattr(live, "btc_regime", lambda d, n: pd.Series([False, False]))
    assert not s.enrich("DOGEUSDT", dict(sig, side="short"))["passes"]


def test_telegram_test_button_reports_missing_config(tmp_path, monkeypatch):
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "BISS_TG_TOKEN", "BISS_TG_CHAT"):
        monkeypatch.delenv(k, raising=False)

    async def run():
        app = dashboard.build_app(_cfg(tmp_path), "pw", need_login=False, cookie_secure=False)
        async with TestClient(TestServer(app)) as c:
            r = await c.post("/api/telegram_test", json={})
            assert r.status == 502 and "not set" in (await r.json())["detail"]
            assert (await c.post("/api/telegram_test", json={})).status == 429      # 30 s between tests
            assert (await c.post("/api/telegram_test", data="x")).status == 400     # JSON only
    asyncio.run(run())
