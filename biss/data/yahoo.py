"""Underlying-market history for TradeFi contracts: Yahoo Finance via yfinance (free, no account).

Used for (a) multi-year daily history that the 2026-listed perps don't have, (b) levels built from the
underlying's regular-session candles, (c) earnings dates. Personal research use; Yahoo data is unofficial and
can contain errors (see docs/ASSUMPTIONS.md)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

SPECIAL = {
    "BRKB": "BRK-B", "SP500": "^GSPC", "NAS100": "^NDX", "US30": "^DJI", "GER40": "^GDAXI", "HK50": "^HSI",
    "KOSPI": "^KS11", "JP225": "^N225", "XAU": "GC=F", "XAUT": "GC=F", "PAXG": "GC=F", "XAG": "SI=F",
    "XPT": "PL=F", "XPD": "PA=F", "XCU": "HG=F", "COPPER": "HG=F", "CL": "CL=F", "BZ": "BZ=F", "NG": "NG=F",
    "NATGAS": "NG=F", "EUR": "EURUSD=X", "GBP": "GBPUSD=X", "AUD": "AUDUSD=X", "JPY": "JPY=X", "CHF": "CHF=X",
    "SKHYNIX": "000660.KS", "SAMSUNG": "005930.KS", "HYUNDAI": "005380.KS", "TENCENT": "0700.HK",
    "XIAOMI": "1810.HK", "TSMC": "2330.TW", "SOFTBANK": "9984.T", "TOYOTA": "7203.T", "SONY": "SONY",
    "XAL": "ALI=F",
}
# contracts with no listed underlying (pre-IPO, synthetic) -> no history
NO_UNDERLYING = {"OPENAI", "ANTHROPIC", "SPCX", "OURA", "YMTC", "MOONSHOT", "POLYMARKET", "KALSHI", "ANDURIL",
                 "UNITREE", "SHEIN", "ZHIPU", "MINIMAX", "CXMT", "DEEPTECH"}


def ticker_for(base: str) -> str | None:
    if base in NO_UNDERLYING:
        return None
    return SPECIAL.get(base, base)


def daily(ticker: str, start: str, cache: Path) -> pd.DataFrame:
    import yfinance as yf

    p = cache / f"{ticker.replace('^', '_').replace('=', '_')}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    d = yf.download(ticker, start=start, progress=False, auto_adjust=True, multi_level_index=False)
    if d.empty:
        return d
    d = d.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    d.index = pd.DatetimeIndex(d.index).tz_localize("UTC").as_unit("ns")
    d["quote_volume"] = d["close"] * d["volume"]
    d = d.dropna()
    cache.mkdir(parents=True, exist_ok=True)
    d.to_parquet(p)
    return d


def earnings_dates(ticker: str, cache: Path, limit: int = 40) -> list[pd.Timestamp]:
    import yfinance as yf

    p = cache / f"earn_{ticker}.csv"
    if p.exists():
        s = pd.read_csv(p)["date"]
        return [pd.Timestamp(x) for x in s]
    try:
        e = yf.Ticker(ticker).get_earnings_dates(limit=limit)
        dates = sorted({pd.Timestamp(x).tz_convert("UTC").normalize() for x in e.index}) if e is not None else []
    except Exception:  # noqa: BLE001
        dates = []
    cache.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates}).to_csv(p, index=False)
    return dates
