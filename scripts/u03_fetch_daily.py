"""Daily Binance klines for every USDT-M perp (live via REST, delisted via data.binance.vision), from 2019.

Used for HTF levels, regimes, point-in-time volume ranks and tiers. Writes data/binance/klines/1d/*.parquet and
data/binance/daily_qv.parquet (date x symbol quote volume).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.data import binance  # noqa: E402
from biss.universe import NON_COIN_INDEXES  # noqa: E402

cfg = config.load()
DD = config.data_dir(cfg)
st = binance.Store(DD)
meta = json.loads((DD / "binance" / "symbols.json").read_text(encoding="utf-8"))
live = set(meta["live"])
syms = sorted(s for s in set(meta["vision"]) | live if s.endswith("USDT") and s not in NON_COIN_INDEXES)
START = cfg.data.warmup_start
start_ms = int(pd.Timestamp(START, tz="UTC").timestamp() * 1000)


def one(sym: str) -> tuple[str, int]:
    p = st.path(sym, "1d")
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        return sym, len(pd.read_parquet(p))
    try:
        if sym in live:
            df = binance.rest_klines(sym, "1d", start_ms)
        else:
            df = binance.vision_monthly_klines(sym, "1d", START)
        if not df.empty:
            df.to_parquet(p)
        return sym, len(df)
    except Exception as e:  # noqa: BLE001
        print("fail", sym, e)
        return sym, -1


if __name__ == "__main__":
    res = binance.parallel(one, syms, workers=16)
    ok = [s for s, n in res if n > 0]
    print(f"{len(ok)}/{len(syms)} symbols with daily data")
    qv = {}
    for s in ok:
        df = st.load(s, "1d")
        qv[s] = df["quote_volume"]
    q = pd.DataFrame(qv).sort_index()
    q.to_parquet(DD / "binance" / "daily_qv.parquet")
    print(q.shape, q.index.min(), q.index.max())
