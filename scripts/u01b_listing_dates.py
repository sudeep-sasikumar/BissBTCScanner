"""Fix listing dates for contracts with >= 1000 WEEX daily bars (binary search on historyKlines)."""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.data import weex  # noqa: E402

REP = config.ROOT / "reports"

if __name__ == "__main__":
    u = pd.read_csv(REP / "universe.csv", keep_default_na=False)
    todo = u[pd.to_numeric(u.weex_daily_bars, errors="coerce") >= 1000].symbol.tolist()

    def f(s):
        try:
            fb = weex.first_bar(s, "1d")
            return s, fb.date() if fb is not None else ""
        except Exception:  # noqa: BLE001
            return s, ""
    with ThreadPoolExecutor(4) as ex:
        res = dict(ex.map(f, todo))
    u["listing_date"] = [res.get(s) or d for s, d in zip(u.symbol, u.listing_date)]
    u.to_csv(REP / "universe.csv", index=False)
    print(len(todo), "updated;", {k: res[k] for k in list(res)[:5]})
