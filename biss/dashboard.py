"""Read-only web dashboard (aiohttp), served from a background thread beside the scanner.

It reads the scanner's state file and the backtest export (biss/web/backtest.json); it never changes
trading state. Same login scheme as LeverageTrading's dashboard.

Environment:
  DASHBOARD_PASSWORD       required whenever the dashboard is reachable beyond localhost
  DASHBOARD_BIND           default 127.0.0.1 (the Docker image sets 0.0.0.0)
  DASHBOARD_PORT           default 8030
  DASHBOARD_COOKIE_SECURE  true when served over HTTPS (set in docker-compose.yaml)
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

from aiohttp import web

from . import config

COOKIE = "biss_session"
SESSION_DAYS = 14
LOCAL = ("127.0.0.1", "localhost", "::1")
WEB = Path(__file__).parent / "web"
INDEX = WEB / "index.html"
BACKTEST = WEB / "backtest.json"

LOGIN_WINDOW_S = 900          # failed logins are counted over 15 minutes
LOGIN_MAX_PER_IP = 5
LOGIN_MAX_TOTAL = 30


def _secret(data_dir: Path) -> bytes:
    path = data_dir / "dashboard.secret"
    if not path.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(secrets.token_bytes(32))
    return path.read_bytes()


def make_token(secret: bytes, days: float = SESSION_DAYS) -> str:
    exp = str(int(time.time() + days * 86400))
    return f"{exp}.{hmac.new(secret, exp.encode(), hashlib.sha256).hexdigest()}"


def valid_token(secret: bytes, token: str | None) -> bool:
    if not token or "." not in token:
        return False
    exp, sig = token.split(".", 1)
    good = hmac.new(secret, exp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, good) and exp.isdigit() and int(exp) > time.time()


def client_ip(request) -> str:
    """Behind Traefik the real client is the LAST X-Forwarded-For entry (the one Traefik appended)."""
    xff = request.headers.get("X-Forwarded-For", "")
    return xff.split(",")[-1].strip() if xff.strip() else (request.remote or "?")


def profile(cfg) -> dict:
    """The strategy the scanner runs, straight from config.yaml (shown on the Strategy tab)."""
    sc, sz, sw, f = cfg.scanner, cfg.sizing, cfg.sweep, cfg.filters
    return {"reclaim": sc.reclaim, "entry": sc.entry, "shorts": bool(sc.shorts), "tiers": list(sc.get("tiers") or []),
            "t1": list(cfg.universe.t1), "top_n": sc.top_n_by_weex_volume, "crypto_only": bool(sc.get("crypto_only")),
            "required_filters": {k: list(v) for k, v in dict(sc.required_filters).items()}
            if isinstance(sc.required_filters, dict) else list(sc.required_filters),
            "min_sweep_atr4h": sw.min_atr4h, "skip_weekend": bool(sw.skip_weekend), "max_atr1d": sw.max_atr1d,
            "max_days_below": sw.max_days_below, "fomc_days": f.fomc_days, "quarter_close_days": f.quarter_close_days,
            "dd_crypto": list(f.dd_crypto), "max_stop_pct": cfg.stop.max_stop_pct, "buffer_atr4h": cfg.stop.buffer_atr4h,
            "buffer_pct": cfg.stop.buffer_pct, "risk": sz.default_risk, "tier_mult": dict(sz.tier_mult),
            "strong_needs_regime": bool(sz.get("strong_needs_regime")),
            "max_open_risk": sz.max_open_risk, "max_per_cluster": sz.get("max_per_cluster"),
            "lev_caps": dict(sz.lev_caps), "liq_buffer_mult": sz.liq_buffer_mult, "paper_equity": sc.paper_equity}


def snapshot(cfg) -> dict:
    p = config.ROOT / cfg.scanner.state_file
    st = {}
    if p.exists():
        try:
            st = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            st = {"error": "state file unreadable (being written?) - retry"}
    closed = st.get("closed", [])
    eq = float(cfg.scanner.paper_equity) + sum(float(t.get("pnl_usd") or 0) for t in closed)
    rs = [float(t["R_gross"]) for t in closed if t.get("R_gross") is not None]
    return {"now": time.time(), "version": os.environ.get("APP_VERSION", "dev")[:7],
            "telegram": bool((os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BISS_TG_TOKEN"))
                             and (os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("BISS_TG_CHAT"))),
            "health": st.get("health", {}), "last_poll": st.get("last_poll"),
            "open": st.get("open", []), "closed": closed[-300:][::-1], "alerts": st.get("alerts", [])[-300:][::-1],
            "recent": st.get("recent", []), "equity": eq,
            "paper_stats": {"n": len(rs), "win": (sum(r > 0 for r in rs) / len(rs)) if rs else None,
                            "avg_r": (sum(rs) / len(rs)) if rs else None, "total_r": sum(rs)},
            "profile": profile(cfg), "error": st.get("error")}


def build_app(cfg, password: str, need_login: bool, cookie_secure: bool) -> web.Application:
    secret = _secret(config.data_dir(cfg))
    cache: dict = {"t": 0.0, "data": None}
    fails: dict[str, list[float]] = {}

    @web.middleware
    async def auth(request: web.Request, handler):
        open_paths = ("/", "/login", "/healthz")
        if need_login and request.path not in open_paths and not valid_token(secret, request.cookies.get(COOKIE)):
            return web.json_response({"error": "login required"}, status=401)
        resp = await handler(request)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    async def index(_r):
        return web.Response(text=INDEX.read_text(encoding="utf-8"), content_type="text/html")

    async def login(request: web.Request):
        now = time.time()
        ip = client_ip(request)
        for k in list(fails):
            fails[k] = [t for t in fails[k] if now - t < LOGIN_WINDOW_S]
            if not fails[k]:
                del fails[k]
        if len(fails.get(ip, [])) >= LOGIN_MAX_PER_IP or sum(map(len, fails.values())) >= LOGIN_MAX_TOTAL:
            return web.json_response({"error": "too many attempts - wait 15 minutes"}, status=429)
        try:
            given = str((await request.json()).get("password", ""))
        except Exception:  # noqa: BLE001
            given = ""
        if not (password and hmac.compare_digest(given.encode(), password.encode())):
            fails.setdefault(ip, []).append(now)
            return web.json_response({"error": "wrong password"}, status=401)
        resp = web.json_response({"ok": True})
        resp.set_cookie(COOKIE, make_token(secret), max_age=SESSION_DAYS * 86400, httponly=True,
                        samesite="Strict", secure=cookie_secure)
        return resp

    async def data(_r):
        if cache["data"] is None or time.time() - cache["t"] > 10:
            cache["data"] = await asyncio.to_thread(snapshot, cfg)
            cache["t"] = time.time()
        return web.json_response(cache["data"])

    async def backtest(_r):
        if not BACKTEST.exists():
            return web.json_response({"error": "no backtest export in this image"}, status=404)
        return web.Response(body=BACKTEST.read_bytes(), content_type="application/json")

    async def healthz(_r):
        return web.json_response({"ok": True})

    app = web.Application(middlewares=[auth])
    app.add_routes([web.get("/", index), web.post("/login", login), web.get("/api/data", data),
                    web.get("/api/backtest", backtest), web.get("/healthz", healthz)])
    return app


def settings() -> dict:
    env = os.environ
    return {"bind": env.get("DASHBOARD_BIND") or "127.0.0.1", "port": int(env.get("DASHBOARD_PORT") or 8030),
            "password": env.get("DASHBOARD_PASSWORD") or "",
            "cookie_secure": (env.get("DASHBOARD_COOKIE_SECURE") or "").lower() in ("1", "true", "yes")}


async def serve(cfg) -> None:
    s = settings()
    need_login = s["bind"] not in LOCAL
    if need_login and not s["password"]:
        print("dashboard is OFF: set DASHBOARD_PASSWORD to enable it beyond localhost", flush=True)
        return
    runner = web.AppRunner(build_app(cfg, s["password"], need_login, s["cookie_secure"]), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, s["bind"], s["port"]).start()
    print(f"dashboard on http://{s['bind']}:{s['port']} (login {'required' if need_login else 'not needed'})", flush=True)
    while True:
        await asyncio.sleep(3600)


def start_in_thread(cfg) -> None:
    def run():
        try:
            asyncio.run(serve(cfg))
        except Exception as e:  # noqa: BLE001
            print("dashboard stopped:", e, flush=True)
    threading.Thread(target=run, name="dashboard", daemon=True).start()


if __name__ == "__main__":   # python -m biss.dashboard  (local, no login)
    asyncio.run(serve(config.load()))
