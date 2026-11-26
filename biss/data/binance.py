"""Binance USDT-M history: data.binance.vision bulk files (delisted contracts included) + fapi REST tail.

Used for crypto (and the few Binance TradeFi perps) because WEEX history is short (see reports/universe.md).
"""
from __future__ import annotations

import io
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

VISION = "https://data.binance.vision/"
S3_LIST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
FAPI = "https://fapi.binance.com"
KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades",
         "taker_buy_base", "taker_buy_quote", "ignore"]
IV_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}

_s = requests.Session()
_s.headers["User-Agent"] = "biss-scanner/0.1"


def _get(url: str, params: dict | None = None, retries: int = 5) -> requests.Response | None:
    for i in range(retries):
        try:
            r = _s.get(url, params=params, timeout=30)
            if r.status_code in (400, 404):  # unknown/invalid symbol: no retry
                return None
            if r.status_code in (418, 429):
                time.sleep(int(r.headers.get("Retry-After", 5)) + i)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == retries - 1:
                raise
            time.sleep(1 + 2 * i)
    return None


def list_um_symbols(kind: str = "klines") -> list[str]:
    """Every symbol that has a folder under data/futures/um/monthly/<kind>/ (live and delisted)."""
    out: list[str] = []
    marker = ""
    prefix = f"data/futures/um/monthly/{kind}/"
    while True:
        r = _get(S3_LIST, {"delimiter": "/", "prefix": prefix, "marker": marker})
        txt = r.text
        found = re.findall(r"<Prefix>" + re.escape(prefix) + r"([^/<]+)/</Prefix>", txt)
        out.extend(found)
        if "<IsTruncated>true</IsTruncated>" not in txt or not found:
            break
        nm = re.findall(r"<NextMarker>([^<]+)</NextMarker>", txt)
        marker = nm[0] if nm else prefix + found[-1] + "/"
    return sorted(set(out))


def _read_zip_csv(content: bytes, cols: list[str]) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        with z.open(z.namelist()[0]) as f:
            raw = f.read()
    first = raw.split(b"\n", 1)[0]
    header = 0 if re.search(rb"[a-zA-Z]", first) else None
    df = pd.read_csv(io.BytesIO(raw), header=header)
    if header is None:
        df.columns = cols[: df.shape[1]]
    else:
        df.columns = [c.strip().lower() for c in df.columns]
    return df


def _norm_klines(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.rename(columns={"count": "trades", "taker_buy_volume": "taker_buy_base"})
    t = pd.to_numeric(df["open_time"], errors="coerce")
    # some 2025+ files are in microseconds
    t = t.where(t < 10**14, t // 1000)
    df = df.assign(open_time=pd.to_datetime(t, unit="ms", utc=True))
    keep = ["open", "high", "low", "close", "volume", "quote_volume"]
    for c in keep:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df.dropna(subset=["open_time"]).drop_duplicates("open_time").set_index("open_time").sort_index()[keep]


def months(start: str, end: pd.Timestamp | None = None) -> list[str]:
    end = end or pd.Timestamp.now(tz="UTC")
    return [p.strftime("%Y-%m") for p in pd.period_range(pd.Timestamp(start), end.tz_localize(None), freq="M")]


def list_keys(prefix: str) -> list[str]:
    """All object keys under a data.binance.vision prefix (S3 listing, paginated)."""
    keys: list[str] = []
    marker = ""
    while True:
        r = _get(S3_LIST, {"prefix": prefix, "marker": marker})
        if r is None:
            break
        found = re.findall(r"<Key>([^<]+)</Key>", r.text)
        keys.extend(found)
        if "<IsTruncated>true</IsTruncated>" not in r.text or not found:
            break
        marker = found[-1]
    return keys


def available_months(symbol: str, interval: str, kind: str = "klines") -> set[str]:
    keys = list_keys(f"data/futures/um/monthly/{kind}/{symbol}/{interval}/")
    return {m.group(1) for k in keys if (m := re.search(r"-(\d{4}-\d{2})\.zip$", k))}


def vision_monthly_klines(symbol: str, interval: str, start: str, kind: str = "klines") -> pd.DataFrame:
    frames = []
    have = available_months(symbol, interval, kind)
    for m in months(start):
        if m not in have:
            continue
        url = f"{VISION}data/futures/um/monthly/{kind}/{symbol}/{interval}/{symbol}-{interval}-{m}.zip"
        r = _get(url)
        if r is None:
            continue
        frames.append(_norm_klines(_read_zip_csv(r.content, KCOLS)))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames).pipe(lambda d: d[~d.index.duplicated()]).sort_index()


def rest_klines(symbol: str, interval: str, start_ms: int, end_ms: int | None = None, kind: str = "klines") -> pd.DataFrame:
    """fapi REST paging (live symbols only). kind: klines | markPriceKlines."""
    end_ms = end_ms or int(time.time() * 1000)
    rows = []
    t = start_ms
    while t < end_ms:
        r = _get(f"{FAPI}/fapi/v1/{kind}", {"symbol": symbol, "interval": interval, "startTime": t,
                                             "endTime": end_ms, "limit": 1500})
        if r is None:
            break
        data = r.json()
        if not isinstance(data, list) or not data:
            break
        rows.extend(data)
        t = int(data[-1][0]) + IV_MS[interval]
        if len(data) < 1500:
            break
    if not rows:
        return pd.DataFrame()
    return _norm_klines(pd.DataFrame([x[:12] for x in rows], columns=KCOLS[: len(rows[0][:12])]))


def funding_rest(symbol: str, start_ms: int) -> pd.Series:
    out = []
    t = start_ms
    while True:
        r = _get(f"{FAPI}/fapi/v1/fundingRate", {"symbol": symbol, "startTime": t, "limit": 1000})
        if r is None:
            break
        d = r.json()
        if not isinstance(d, list) or not d:
            break
        out.extend(d)
        t = int(d[-1]["fundingTime"]) + 1
        if len(d) < 1000:
            break
    if not out:
        return pd.Series(dtype=float)
    s = pd.Series([float(x["fundingRate"]) for x in out],
                  index=pd.to_datetime([int(x["fundingTime"]) for x in out], unit="ms", utc=True))
    return s[~s.index.duplicated()].sort_index()


def funding_vision(symbol: str, start: str) -> pd.Series:
    parts = []
    for m in months(start):
        r = _get(f"{VISION}data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{m}.zip")
        if r is None:
            continue
        df = _read_zip_csv(r.content, ["calc_time", "funding_interval_hours", "last_funding_rate"])
        t = pd.to_numeric(df["calc_time"])
        parts.append(pd.Series(pd.to_numeric(df["last_funding_rate"]).values,
                               index=pd.to_datetime(t, unit="ms", utc=True)))
    if not parts:
        return pd.Series(dtype=float)
    s = pd.concat(parts)
    return s[~s.index.duplicated()].sort_index()


class Store:
    """Parquet cache: <data>/binance/<kind>/<interval>/<SYMBOL>.parquet"""

    def __init__(self, root: Path):
        self.root = Path(root) / "binance"

    def path(self, symbol: str, interval: str, kind: str = "klines") -> Path:
        return self.root / kind / interval / f"{symbol}.parquet"

    def load(self, symbol: str, interval: str, kind: str = "klines") -> pd.DataFrame:
        p = self.path(symbol, interval, kind)
        return pd.read_parquet(p) if p.exists() else pd.DataFrame()

    def update(self, symbol: str, interval: str, start: str, live: bool, kind: str = "klines") -> pd.DataFrame:
        """Fill from vision monthly files, then REST tail for live symbols. Idempotent and incremental."""
        p = self.path(symbol, interval, kind)
        p.parent.mkdir(parents=True, exist_ok=True)
        old = self.load(symbol, interval, kind)
        if old.empty:
            df = vision_monthly_klines(symbol, interval, start, kind)
        else:
            # re-pull from the start of the last stored month (it may have been a partial REST tail)
            last = old.index[-1]
            df_new = vision_monthly_klines(symbol, interval, last.strftime("%Y-%m-01"), kind)
            df = pd.concat([old, df_new])
        if live:
            from_ms = int(df.index[-1].timestamp() * 1000) + IV_MS[interval] if not df.empty else \
                int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
            tail = rest_klines(symbol, interval, from_ms, kind=kind)
            if not tail.empty:
                df = pd.concat([df, tail]) if not df.empty else tail
        if df.empty:
            return df
        df = df[~df.index.duplicated(keep="last")].sort_index()
        df.to_parquet(p)
        return df


def parallel(fn, items, workers: int = 12):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))
