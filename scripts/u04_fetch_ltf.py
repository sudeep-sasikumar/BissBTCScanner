"""15m Binance klines (and funding) for every symbol that was T1/T2/T3 on any day of the signal period,
plus Binance TradeFi perps that map to WEEX contracts (T4). Vision monthly files + REST tail."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.data import binance  # noqa: E402
from biss.tiers import crypto_tiers  # noqa: E402

cfg = config.load()
DD = config.data_dir(cfg)
st = binance.Store(DD)
meta = json.loads((DD / "binance" / "symbols.json").read_text(encoding="utf-8"))
live = set(meta["live"])
LTF_START = (pd.Timestamp(cfg.data.start) - pd.Timedelta(days=45)).strftime("%Y-%m-%d")


def targets() -> list[str]:
    t = crypto_tiers()
    t = t[t.index >= pd.Timestamp(cfg.data.start, tz="UTC")]
    crypto = [c for c in t.columns if (t[c] != "").sum() >= 30]  # >= 30 point-in-time tier days
    u = pd.read_csv(config.ROOT / "reports" / "universe.csv")
    tradfi = u[(u.asset_class != "crypto") & u.binance_symbol.notna()].binance_symbol.unique().tolist()
    return sorted(set(crypto)), sorted(set(tradfi))


def fetch(sym: str) -> tuple[str, int, int]:
    try:
        df = st.update(sym, "15m", LTF_START, live=sym in live)
        p = DD / "binance" / "funding" / f"{sym}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            if sym in live:
                f = binance.funding_rest(sym, int(pd.Timestamp(LTF_START, tz="UTC").timestamp() * 1000))
            else:
                f = binance.funding_vision(sym, LTF_START)
            f.rename("rate").to_frame().to_parquet(p)
        else:
            f = pd.read_parquet(p)
        return sym, len(df), len(f)
    except Exception as e:  # noqa: BLE001
        print("fail", sym, e, flush=True)
        return sym, -1, -1


if __name__ == "__main__":
    crypto, tradfi = targets()
    print(f"crypto {len(crypto)}, tradfi {len(tradfi)}", flush=True)
    res = binance.parallel(fetch, crypto + tradfi, workers=16)
    bad = [s for s, n, _ in res if n <= 0]
    print("done; empty/failed:", len(bad), bad[:20])
