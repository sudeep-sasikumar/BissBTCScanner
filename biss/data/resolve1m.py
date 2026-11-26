"""1m bars inside an ambiguous 15m bar (stop and target both touched) to decide which came first (8.5).
Source: data.binance.vision daily 1m files, cached per symbol-day. No 1m data -> stop first."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import binance

NS_15M = 15 * 60 * 10**9


class Resolver:
    def __init__(self, root: Path, symbol: str):
        self.dir = Path(root) / "binance" / "klines" / "1m_days" / symbol
        self.symbol = symbol
        self.mem: dict[str, pd.DataFrame] = {}
        self.calls = 0
        self.missing = 0

    def _day(self, day: str) -> pd.DataFrame:
        if day in self.mem:
            return self.mem[day]
        p = self.dir / f"{day}.parquet"
        if p.exists():
            df = pd.read_parquet(p)
        else:
            url = f"{binance.VISION}data/futures/um/daily/klines/{self.symbol}/1m/{self.symbol}-1m-{day}.zip"
            r = binance._get(url)
            df = binance._norm_klines(binance._read_zip_csv(r.content, binance.KCOLS)) if r is not None else pd.DataFrame()
            if df.empty:
                t0 = pd.Timestamp(day, tz="UTC")
                df = binance.rest_klines(self.symbol, "1m", int(t0.timestamp() * 1000),
                                         int((t0 + pd.Timedelta(days=1)).timestamp() * 1000) - 1)
            self.dir.mkdir(parents=True, exist_ok=True)
            df.to_parquet(p)
        self.mem[day] = df
        return df

    def make(self, sign: int):
        def first(t_ns: int, stop_dir: float, tgt_dir: float) -> str:
            self.calls += 1
            t = pd.Timestamp(t_ns, tz="UTC")
            try:
                df = self._day(t.strftime("%Y-%m-%d"))
            except Exception:  # noqa: BLE001
                df = pd.DataFrame()
            if df.empty:
                self.missing += 1
                return "stop"
            seg = df[(df.index >= t) & (df.index < t + pd.Timedelta(minutes=15))]
            if seg.empty:
                self.missing += 1
                return "stop"
            for _, r in seg.iterrows():
                lo = r["low"] if sign > 0 else -r["high"]
                hi = r["high"] if sign > 0 else -r["low"]
                if lo <= stop_dir:
                    return "stop"  # includes a 1m bar touching both
                if hi >= tgt_dir:
                    return "tgt"
            return "stop"
        return first
