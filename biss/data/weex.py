"""WEEX USDT-M futures public market API (no keys, read-only).

Verified against the live API on 2026-11-25 (see docs/ASSUMPTIONS.md):
- base https://api-contract.weex.com, prefix /capi/v3/market/
- exchangeInfo: 1016 symbols; contractType PERPETUAL | TRADIFI_PERPETUAL; underlyingType COIN | Stocks |
  Indices | Metals | Forex | Commodities | Pre-IPO; makerFeeRate/takerFeeRate per symbol.
- riskLimits: list of {symbol, brackets[{bracket, notionalFloor, notionalCap, initialLeverage, maintMarginRatio}]}.
- klines: newest-first, limit <= 1000, no paging.
- historyKlines: needs BOTH startTime and endTime, range <= 90 days, limit <= 100, priceType LAST|INDEX|MARK.
- rate limit REQUEST_WEIGHT 500 / 10 s (historyKlines weight 5).
"""
from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests

BASE = "https://api-contract.weex.com/capi/v3/market/"
INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000,
               "4h": 14_400_000, "12h": 43_200_000, "1d": 86_400_000, "1w": 604_800_000}
MAX_RANGE_MS = 89 * 86_400_000

_session = requests.Session()
_session.headers["User-Agent"] = "biss-scanner/0.1"


def get(path: str, params: dict[str, Any] | None = None, retries: int = 5) -> Any:
    for i in range(retries):
        try:
            r = _session.get(BASE + path, params=params, timeout=20)
            if r.status_code == 429:
                time.sleep(2 + 2 * i)
                continue
            data = r.json()
            if isinstance(data, dict) and "code" in data and data.get("code") not in (0, "0", 200, "200"):
                if str(data.get("code")) in ("-1003", "429"):
                    time.sleep(2 + 2 * i)
                    continue
                raise WeexError(f"{path} {params}: {data}")
            return data
        except (requests.RequestException, ValueError):
            if i == retries - 1:
                raise
            time.sleep(1 + i)
    raise WeexError(f"{path}: retries exhausted")


class WeexError(RuntimeError):
    pass


def exchange_info() -> dict:
    return get("exchangeInfo")


def risk_limits() -> list[dict]:
    return get("riskLimits")


def ticker_24h() -> list[dict]:
    return get("ticker/24hr")


def funding_history(symbol: str, start_ms: int | None = None, end_ms: int | None = None, limit: int = 1000) -> list[dict]:
    p: dict[str, Any] = {"symbol": symbol, "limit": limit}
    if start_ms is not None:
        p["startTime"] = start_ms
    if end_ms is not None:
        p["endTime"] = end_ms
    return get("fundingRate", p)


COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote"]


def _frame(rows: list[list]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "quote_volume"])
    df = pd.DataFrame([r[: len(COLS)] for r in rows], columns=COLS[: len(rows[0])])
    for c in ("open", "high", "low", "close", "volume", "quote_volume"):
        if c in df:
            df[c] = df[c].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"].astype("int64"), unit="ms", utc=True)
    df = df.drop_duplicates("open_time").set_index("open_time").sort_index()
    return df[[c for c in ("open", "high", "low", "close", "volume", "quote_volume") if c in df]]


def klines_recent(symbol: str, interval: str, limit: int = 1000) -> pd.DataFrame:
    return _frame(get("klines", {"symbol": symbol, "interval": interval, "limit": limit}))


def history_klines(symbol: str, interval: str, start_ms: int, end_ms: int, price_type: str = "LAST") -> pd.DataFrame:
    """Page through historyKlines (100 rows, <= 89-day windows)."""
    step = min(MAX_RANGE_MS, 100 * INTERVAL_MS[interval])
    out = []
    t = start_ms
    while t <= end_ms:
        e = min(t + step - 1, end_ms, int(time.time() * 1000) - 120_000)
        if e < t:
            break
        rows = get("historyKlines", {"symbol": symbol, "interval": interval, "startTime": t, "endTime": e,
                                      "limit": 100, "priceType": price_type})
        if rows:
            out.extend(rows)
        t = e + 1
    return _frame(out)


def first_bar(symbol: str, interval: str, lo_ms: int = 1_483_228_800_000) -> pd.Timestamp | None:
    """Earliest bar WEEX serves for symbol/interval: binary search on 89-day windows that return data."""
    now = int(time.time() * 1000) - 120_000  # server rejects endTime even slightly in the future
    span = min(MAX_RANGE_MS, 100 * INTERVAL_MS[interval])

    def has(t: int) -> bool:
        rows = get("historyKlines", {"symbol": symbol, "interval": interval, "startTime": t,
                                      "endTime": min(t + span - 1, now - 1), "limit": 100})
        return bool(rows)

    hi = now - span
    if not has(hi):
        return None
    lo = lo_ms
    if has(lo):
        hi = lo
    else:
        while hi - lo > span:
            mid = (lo + hi) // 2
            if has(mid):
                hi = mid
            else:
                lo = mid
    # no bars in [lo, lo+span] and hi - lo <= span, so the first bar is inside [hi, hi+span)
    rows = get("historyKlines", {"symbol": symbol, "interval": interval, "startTime": hi,
                                  "endTime": min(hi + span - 1, now - 1), "limit": 100})
    if not rows:
        return None
    return pd.to_datetime(min(int(r[0]) for r in rows), unit="ms", utc=True)
