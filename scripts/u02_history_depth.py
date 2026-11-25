"""Section 3.2 / 3.3: WEEX history depth per timeframe, and TradeFi market-closed behaviour.

Writes reports/history_depth.csv and reports/tradfi_hours.csv.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.data import binance, weex  # noqa: E402

cfg = config.load()
REP = config.ROOT / "reports"
u = pd.read_csv(REP / "universe.csv")

SAMPLE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "HYPEUSDT", "ZECUSDT", "DOGEUSDT", "XRPUSDT", "LINKUSDT",
          "AAPLUSDT", "NVDAUSDT", "TSLAUSDT", "SPYUSDT", "QQQUSDT", "XAUUSDT", "CLUSDT", "EURUSDT",
          "SP500USDT", "NAS100USDT", "MSTRUSDT", "COINUSDT"]
IVS = ["1w", "1d", "4h", "15m", "1m"]


def depth(sym: str) -> dict:
    row = {"symbol": sym}
    for iv in IVS:
        try:
            fb = weex.first_bar(sym, iv)
        except Exception as e:  # noqa: BLE001
            fb = f"err {e}"[:40]
        row[f"weex_first_{iv}"] = fb
    try:
        row["weex_first_15m_mark"] = weex.first_bar(sym, "15m") if False else None
        f = weex.funding_history(sym, limit=1000)
        row["weex_funding_rows"] = len(f) if isinstance(f, list) else None
        if isinstance(f, list) and f:
            row["weex_funding_first"] = pd.to_datetime(min(int(x["fundingTime"]) for x in f), unit="ms", utc=True)
    except Exception as e:  # noqa: BLE001
        row["weex_funding_rows"] = f"err {e}"[:40]
    bn = u.set_index("symbol").get("binance_symbol", pd.Series()).get(sym)
    row["binance_symbol"] = bn
    if isinstance(bn, str):
        r = binance._get(binance.FAPI + "/fapi/v1/klines", {"symbol": bn, "interval": "1d", "startTime": 0, "limit": 1})
        if r is not None and r.json():
            row["binance_first_1d"] = pd.to_datetime(int(r.json()[0][0]), unit="ms", utc=True)
    return row


def closed_behaviour(sym: str) -> dict:
    """Last ~40 days of WEEX 1h bars: do TradeFi perps trade on weekends / overnight, and how?"""
    df = weex.klines_recent(sym, "1h", 1000)
    if df.empty:
        return {"symbol": sym}
    df = df[df.index >= df.index[-1] - pd.Timedelta(days=40)]
    df["wk"] = df.index.day_of_week >= 5
    df["flat"] = (df["high"] - df["low"]) <= 1e-12
    df["rng"] = (df["high"] - df["low"]) / df["close"]
    wk, wd = df[df.wk], df[~df.wk]
    # weekday US cash-session hours (14:30-21:00 UTC, approx; DST ignored) vs the rest
    hr = df.index.hour + df.index.minute / 60
    sess = (~df.wk) & (hr >= 14) & (hr < 21)
    off = (~df.wk) & ~sess
    return {
        "symbol": sym, "hours": len(df),
        "weekend_bars": int(df.wk.sum()), "weekend_flat_pct": round(100 * wk.flat.mean(), 1) if len(wk) else None,
        "weekend_med_range_pct": round(100 * wk.rng.median(), 3) if len(wk) else None,
        "weekend_med_qvol": round(wk.quote_volume.median(), 0) if len(wk) else None,
        "us_session_med_range_pct": round(100 * df[sess].rng.median(), 3),
        "us_session_med_qvol": round(df[sess].quote_volume.median(), 0),
        "weekday_offhours_med_range_pct": round(100 * df[off].rng.median(), 3),
        "weekday_offhours_med_qvol": round(df[off].quote_volume.median(), 0),
        "max_gap_mon_open_pct": round(100 * _monday_gap(df), 2),
    }


def _monday_gap(df: pd.DataFrame) -> float:
    """Largest |Fri 21:00 close -> Mon 13:30 open| move seen (gap risk through a stop)."""
    c = df["close"]
    gaps = []
    for d in df.index.normalize().unique():
        if d.day_of_week != 0:
            continue
        fri = c[(c.index < d - pd.Timedelta(days=2)) & (c.index >= d - pd.Timedelta(days=3))]
        mon = df[(df.index >= d + pd.Timedelta(hours=13)) & (df.index < d + pd.Timedelta(hours=15))]
        if len(fri) and len(mon):
            gaps.append(abs(mon["open"].iloc[0] / fri.iloc[-1] - 1))
    return max(gaps) if gaps else float("nan")


if __name__ == "__main__":
    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(depth, SAMPLE))
    pd.DataFrame(rows).to_csv(REP / "history_depth.csv", index=False)
    print(pd.DataFrame(rows).to_string())
    tf = u[u.asset_class != "crypto"].sort_values("vol_30d_usd", ascending=False).head(25).symbol.tolist()
    with ThreadPoolExecutor(4) as ex:
        hrs = list(ex.map(closed_behaviour, tf + ["BTCUSDT"]))
    pd.DataFrame(hrs).to_csv(REP / "tradfi_hours.csv", index=False)
    print(pd.DataFrame(hrs).to_string())
