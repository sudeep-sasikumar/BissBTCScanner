"""Calendar filters (F3): FOMC decisions, quarterly candle closes, weekends, earnings hook.

FOMC decision dates (second day of each meeting) for 2022-2026 are from the Federal Reserve's published
calendars; 2027 dates are the Fed's tentative schedule and MUST be re-checked before live use
(docs/ASSUMPTIONS.md).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FOMC = [
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    # tentative, verify:
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28", "2027-09-22", "2027-10-27", "2027-12-08",
]
# decision announced 14:00 New York = 18:00 or 19:00 UTC; use 19:00 UTC
FOMC_TS = pd.to_datetime(FOMC).tz_localize("UTC") + pd.Timedelta(hours=19)


def days_to_fomc(ts: pd.Timestamp) -> float:
    """Signed days from ts to the nearest FOMC decision (negative = decision already happened)."""
    d = (FOMC_TS - ts) / pd.Timedelta(days=1)
    return float(d[np.argmin(np.abs(d))])


def near_fomc(ts: pd.Timestamp, days: float = 7) -> bool:
    return abs(days_to_fomc(ts)) <= days


def days_to_quarter_close(ts: pd.Timestamp) -> float:
    """Days to the nearest quarterly candle boundary (1 Jan/Apr/Jul/Oct 00:00 UTC)."""
    y = ts.year
    bounds = [pd.Timestamp(f"{yy}-{m:02d}-01", tz="UTC") for yy in (y - 1, y, y + 1) for m in (1, 4, 7, 10)]
    return float(min(abs((b - ts) / pd.Timedelta(days=1)) for b in bounds))


def is_weekend(ts: pd.Timestamp) -> bool:
    return ts.day_of_week >= 5


def us_market_closed(ts: pd.Timestamp) -> bool:
    """Approximate US cash-session closure (weekends, outside 13:30-20:00 UTC, ignoring DST/holidays).
    Used to flag TradeFi sweeps whose low printed while the underlying market was shut."""
    if ts.day_of_week >= 5:
        return True
    h = ts.hour + ts.minute / 60
    return not (13.5 <= h < 21.0)


def near_earnings(symbol: str, ts: pd.Timestamp, sessions: int = 2, calendar: dict | None = None) -> bool | None:
    """Earnings filter hook. Returns None when no earnings calendar is configured (needs a data provider;
    see docs/ASSUMPTIONS.md)."""
    if not calendar or symbol not in calendar:
        return None
    dates = pd.to_datetime(calendar[symbol]).tz_localize("UTC")
    bdays = np.abs(np.busday_count(ts.date(), [d.date() for d in dates]))
    return bool((bdays <= sessions).any())
