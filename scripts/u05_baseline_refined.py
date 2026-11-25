"""Reproduce the refined weekly-close baseline (R3/E1) on Binance daily data, point-in-time top 50.
Documented: 158 trades, 68% win, +0.97R after fees (Oct 2022 - Oct 2026). Writes reports/baseline_refined.csv."""
from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.baselines import refined_weekly  # noqa: E402
from biss.data import binance  # noqa: E402
from biss.indicators import btc_regime  # noqa: E402
from biss.metrics import stats  # noqa: E402
from biss.tiers import crypto_tiers  # noqa: E402
from biss.universe import point_in_time_ranks  # noqa: E402

cfg = config.load()
DD = config.data_dir(cfg)
st = binance.Store(DD)


def ranks() -> pd.DataFrame:
    t = crypto_tiers()
    q = pd.read_parquet(DD / "binance" / "daily_qv.parquet")[t.columns]
    return point_in_time_ranks(q, 30).shift(1)


def one(args):
    sym, flip, fee, maker, kw = args
    btc = st.load("BTCUSDT", "1d")
    bull = btc_regime(btc, flip)
    d = st.load(sym, "1d")
    if d.empty:
        return []
    return refined_weekly(sym, d, bull, cfg.data.start, fee=fee, maker=maker, **kw)


def run(flip=1, fee=0.0005, maker=None, end=None, **kw) -> pd.DataFrame:
    rk = ranks()
    syms = list(rk.columns)
    with ProcessPoolExecutor(8) as ex:
        res = list(ex.map(one, [(s, flip, fee, maker, kw) for s in syms], chunksize=8))
    df = pd.DataFrame([r for rr in res for r in rr])
    if df.empty:
        return df
    df["rank"] = [rk.at[t.normalize() - pd.Timedelta(days=7), s] if (t.normalize() - pd.Timedelta(days=7)) in rk.index else 999
                  for s, t in zip(df.symbol, df.entry_time)]
    if end:
        df = df[df.entry_time <= pd.Timestamp(end, tz="UTC")]
    return df


if __name__ == "__main__":
    out = []
    for name, kw in [("doc costs (0.05%/side), flip 1d", dict(flip=1, fee=0.0005)),
                     ("WEEX costs (taker 0.08%, maker TP 0.02%), flip 2d", dict(flip=2, fee=0.0008, maker=0.0002))]:
        df = run(**kw)
        df.to_csv(config.ROOT / "reports" / f"baseline_refined_{'doc' if kw['fee']==0.0005 else 'weex'}.csv", index=False)
        top50 = df[df["rank"] <= 50]
        kept = top50[top50.kept]
        for lab, sub in [("all kept, top50", kept), ("to 28 Oct 2026", kept[kept.entry_time <= "2026-10-28"]),
                         ("+ stop<=12%", kept[kept.stop_pct <= 0.12])]:
            s = stats(sub)
            s["variant"] = f"{name}: {lab}"
            out.append(s)
            print(s["variant"], s["trades"], s.get("win%"), s.get("avgR"))
    pd.DataFrame(out).to_csv(config.ROOT / "reports" / "baseline_refined_summary.csv", index=False)
