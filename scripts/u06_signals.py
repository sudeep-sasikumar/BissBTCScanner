"""Generate and simulate every raw signal for every symbol with 15m data (resumable).

  python scripts/u06_signals.py main     # R1/R2/R3d/R3w x E1/E2 x all managements, longs + shorts
  python scripts/u06_signals.py ruleC    # 4h rule C baseline
Output: data/signals/<tag>/<SYMBOL>.parquet
"""
from __future__ import annotations

import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.baselines import RULE_C_OVERRIDES  # noqa: E402
from biss.pipeline import run_symbol  # noqa: E402

cfg0 = config.load()
DD = config.data_dir(cfg0)


def job(args):
    sym, tag = args
    out = DD / "signals" / tag / f"{sym}.parquet"
    if out.exists():
        return sym, -2, 0.0
    t = time.time()
    try:
        if tag == "ruleC":
            cfg = cfg0.override(**RULE_C_OVERRIDES)
            df = run_symbol(sym, cfg, variants=("R2",), entries=("E1",),
                            mgmts=("partial_1r_be", "fixed_2r", "fixed_3r"), tag=tag)
        else:
            df = run_symbol(sym, cfg0, tag=tag)
        out.parent.mkdir(parents=True, exist_ok=True)
        df = df.copy()
        for c in df.columns:  # parquet-friendly
            if df[c].dtype == object:
                df[c] = df[c].astype(str) if not c.endswith("_time") and c not in (
                    "level_valid_from", "level_pivot_time", "last_touch") else df[c]
        df.to_parquet(out)
        return sym, len(df), time.time() - t
    except Exception:  # noqa: BLE001
        print("FAIL", sym, traceback.format_exc()[-600:], flush=True)
        return sym, -1, time.time() - t


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "main"
    only = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    syms = sorted(p.stem for p in (DD / "binance" / "klines" / "15m").glob("*.parquet"))
    if only:
        syms = [s for s in syms if s in only]
    # majors first so partial results are useful early
    pri = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "HYPEUSDT", "ZECUSDT"]
    syms = [s for s in pri if s in syms] + [s for s in syms if s not in pri]
    print(tag, len(syms), "symbols", flush=True)
    done = 0
    with ProcessPoolExecutor(8) as ex:
        futs = [ex.submit(job, (s, tag)) for s in syms]
        for f in as_completed(futs):
            sym, n, secs = f.result()
            done += 1
            if done % 25 == 0 or n == -1:
                print(f"{done}/{len(syms)} {sym} rows={n} {secs:.0f}s", flush=True)
    print("finished", flush=True)
