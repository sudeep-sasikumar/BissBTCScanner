"""Resampling, ATR, moving averages, BTC regime. All outputs are aligned so that the value at bar t uses
only bars that CLOSED at or before t's open (callers shift explicitly where noted)."""
from __future__ import annotations

import numpy as np
import pandas as pd

AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "quote_volume": "sum"}


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """rule: '4h', '1D', 'W' (weeks start Monday 00:00 UTC, like Binance), 'M' (calendar month), 'Y'."""
    if df.empty:
        return df
    cols = {k: v for k, v in AGG.items() if k in df}
    if rule == "W":
        out = df.resample("W-MON", label="left", closed="left").agg(cols)
    elif rule == "M":
        out = df.resample("MS").agg(cols)
    elif rule == "Y":
        out = df.resample("YS").agg(cols)
    else:
        out = df.resample(rule, label="left", closed="left").agg(cols)
    return out.dropna(subset=["open"])


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder ATR; value at bar t includes bar t (shift(1) to use as-of the next bar's open)."""
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def btc_regime(btc_daily: pd.DataFrame, flip_days: int = 2, bear: bool = False) -> pd.Series:
    """True = bull (close > SMA200 and SMA50 > SMA200), with a flip only after `flip_days` consecutive days
    of the new state. Value on day d is known at d's close; use .shift(1) for decisions during day d+1.
    bear=True: the mirror, True = bear (close < SMA200 and SMA50 < SMA200)."""
    c = -btc_daily["close"] if bear else btc_daily["close"]
    s200, s50 = c.rolling(200).mean(), c.rolling(50).mean()
    raw = ((c > s200) & (s50 > s200)).to_numpy()
    valid = s200.notna().to_numpy()
    out = np.zeros(len(c), dtype=bool)
    state, run = False, 0
    for i in range(len(c)):
        if not valid[i]:
            out[i] = False
            continue
        if raw[i] != state:
            run += 1
            if run >= flip_days:
                state, run = raw[i], 0
        else:
            run = 0
        out[i] = state
    return pd.Series(out, index=c.index)


def to_np_ns(idx: pd.DatetimeIndex) -> np.ndarray:
    return idx.as_unit("ns").asi8
