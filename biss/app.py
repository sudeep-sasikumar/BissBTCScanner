"""VPS entry point: the paper scanner (main thread) plus the read-only dashboard (background thread).

  python -m biss.app

PAPER ONLY: market data is read without API keys and no order is ever sent.
Environment: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DASHBOARD_PASSWORD, DOMAIN, DASHBOARD_PATH (default /biss).
"""
from __future__ import annotations

import os
import time
import traceback

from . import config, dashboard
from .collect.collector import Collector
from .scanner import telegram
from .scanner.live import Scanner


def dashboard_url() -> str | None:
    dom = os.environ.get("DOMAIN")
    return f"https://{dom}{os.environ.get('DASHBOARD_PATH', '/biss')}/" if dom else None


def main() -> None:
    cfg = config.load()
    dashboard.start_in_thread(cfg)
    ver = os.environ.get("APP_VERSION", "dev")[:7]
    wait = 30
    while True:                               # WEEX unreachable at boot: retry instead of crash-looping
        try:
            sc = Scanner(cfg)
            break
        except Exception:  # noqa: BLE001
            print("scanner init failed, retrying in", wait, "s\n", traceback.format_exc()[-400:], flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 600)
    if (cfg.get("collect") or {}).get("enabled", True):
        try:
            sc.collector = Collector(cfg)
            sc.collector.event("start", None, {"version": ver, "symbols": sc.symbols})
            sc.collector.start_background()
        except Exception:  # noqa: BLE001
            print("collector disabled:", traceback.format_exc()[-400:], flush=True)
    missing = [k for k in ("DASHBOARD_PASSWORD",) if not os.environ.get(k)]
    url = dashboard_url()
    telegram.send(
        f"BissBTC paper scanner started (version {ver}).\n"
        f"{len(sc.symbols)} symbols, {cfg.scanner.reclaim}/{cfg.scanner.entry}, "
        f"{'longs + shorts' if cfg.scanner.shorts else 'longs'}, risk {cfg.sizing.default_risk:.0%} x conviction, "
        f"open-risk cap {cfg.sizing.max_open_risk:.0%}. Paper alerts only - no orders.\n"
        + (f"Dashboard: {url}" if url and not missing else "Dashboard OFF: set DASHBOARD_PASSWORD"))
    print(f"paper scanner: {len(sc.symbols)} symbols, telegram {'on' if telegram.configured() else 'OFF'}", flush=True)
    while True:
        t0 = time.time()
        try:
            sc.poll()
        except Exception:  # noqa: BLE001
            print("poll fail", traceback.format_exc()[-500:], flush=True)
        time.sleep(max(5.0, cfg.scanner.poll_seconds - (time.time() - t0)))


if __name__ == "__main__":
    main()
