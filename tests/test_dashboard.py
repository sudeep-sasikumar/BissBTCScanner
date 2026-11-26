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
