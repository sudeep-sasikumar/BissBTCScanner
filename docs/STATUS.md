# Build status (25 Nov 2026)

## Done
- `config.yaml`: every `{{ }}` parameter from BUILD_PROMPT.md.
- WEEX client (`biss/data/weex.py`), checked against the live API: 1,016 contracts (560 crypto, 456 TradFi). Fees are taker 0.08% / maker 0.02%, not 0.05%. `historyKlines` needs both start and end, caps at 90 days and 100 rows, and rejects an end time in the future. `klines` returns newest first.
- Universe report data: `reports/universe.csv` (`scripts/u01_universe.py`).
- History depth (`reports/history_depth.csv`): WEEX 15m/1m starts Oct 2023 (BTC/ETH daily from Dec 2019). TradFi perps start Jan 2026 on WEEX and Jan–Apr 2026 on Binance, so crypto uses Binance history.
- TradFi closed-market behaviour (`reports/tradfi_hours.csv`): the perps trade 24/7 and are never flat. Weekend ranges are about ¼ of the US session, and Monday gaps reach 2–10%.
- Binance daily data for 918 USDT perps, delisted ones included; point-in-time tiers (`biss/tiers.py`).
- Engine: levels (`biss/levels.py`), sweep / reclaim R1, R2, R3d, R3w / entry E1, E2 / attempts (`biss/setups.py`), exits with 1m resolution, gaps, fees, slippage and funding (`biss/trade.py`), sizing and liquidation (`biss/sizing.py`), portfolio modes a/b with shuffles (`biss/portfolio.py`), analysis (`biss/analysis.py`), report (`scripts/u07_report.py`, not run yet).
- Refined weekly baseline reproduced (`scripts/u05_baseline_refined.py`): 169 trades, 63% win, +0.49R, median hold 15 days. The doc says 158 trades, 68%, +0.97R. Trade counts and years match; average R is about half. Not yet explained.
- BTC 58.9k reference case is detected by R1 and R2.

## Left
1. Finish the 15m and funding download (`scripts/u04_fetch_ltf.py`, resumable; was about 43% done).
2. `python scripts/u06_signals.py main`, then `... ruleC` (about 8 s per symbol, 8 processes).
3. `python scripts/u07_report.py`, then debug and write the verdict.
4. Mark-price stop check; F6 open interest (not implemented); earnings filter (needs a data provider).
5. Scanner: WEEX live loop plus Telegram via env `BISS_TG_TOKEN` / `BISS_TG_CHAT`. Only for tiers that pass section 8.
6. Tests, README, then a push to GitHub (not yet approved).

## Needs a decision from Sudeep
- TradFi (T4): perp history is under 1 year, too short for weekly/monthly levels. Testing level source (b), the underlying's regular-session candles, and the earnings filter needs a stock data provider. Which one (for example free Stooq or Yahoo, or a paid one)?
