# BissBTC HTF sweep → LTF reclaim: WEEX backtest and paper scanner

A mechanical version of BissBTC's setup. A monthly or weekly level is swept, then reclaimed, and the trade is entered on 15m. The build covers the full WEEX USDT-M universe (crypto and TradeFi), validated as BUILD_PROMPT.md section 8 asks. **Paper only: no API keys, no orders.**

- Spec: [BUILD_PROMPT.md](BUILD_PROMPT.md), with the reference docs in `docs/` (pack notes: [docs/PACK_README.md](docs/PACK_README.md)).
- Results: [reports/backtest.md](reports/backtest.md) (crypto), [reports/tradfi.md](reports/tradfi.md) (TradeFi), [reports/universe.md](reports/universe.md) (WEEX universe), `reports/journal.csv` (trade journal).
- Assumptions and gaps: [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md).

## Layout
| Path | What |
|---|---|
| `config.yaml` | every tunable from the prompt (`{{ }}` values) |
| `biss/data/` | WEEX REST client, Binance bulk/REST history, 1m resolver, Yahoo (TradeFi underlyings) |
| `biss/levels.py` | validated weekly/monthly pivots, opens, prior range extremes, zones (no lookahead) |
| `biss/setups.py` | sweep → reclaim (R1 15m, R2 4h, R3d daily, R3w weekly) → entry (E1/E2), attempts, stop, targets, flags |
| `biss/trade.py` | exits on 15m: stop first, 1m for ambiguous bars, gap fills, fees, slippage, funding, 7 management variants |
| `biss/sizing.py`, `biss/portfolio.py` | risk-based size, leverage as an output, WEEX brackets, liquidation buffer; account modes (a)/(b), 300 shuffles |
| `biss/analysis.py` | filters F1–F5, tiers, slices (IS/OOS/holdout), dedupe |
| `biss/baselines.py` | refined weekly-close rules and rule C |
| `biss/scanner/` | 24/7 paper scanner + Telegram |
| `scripts/u01…u09` | pipeline steps (below) |

## Reproduce (Python 3.12)
```
python -m venv .venv && .venv/Scripts/pip install pandas numpy pyarrow requests pyyaml pytest yfinance
python scripts/u01_universe.py            # WEEX contract list, brackets, fees, volumes
python scripts/u01b_listing_dates.py
python scripts/u02_history_depth.py       # WEEX history depth + TradeFi closed-market behaviour
python scripts/u03_fetch_daily.py         # Binance daily, all USDT perps incl. delisted
python scripts/u04_fetch_ltf.py           # Binance 15m + funding for tiered symbols (~2 GB)
python scripts/u05_baseline_refined.py    # refined weekly baseline
python scripts/u06_signals.py main        # all variants, all symbols (8 processes)
python scripts/u06_signals.py ruleC
python scripts/u07_report.py              # reports/backtest.md + journal
python scripts/u08_tradfi.py              # reports/tradfi.md
python scripts/u09_universe_md.py         # reports/universe.md
python -m pytest
```

## Paper scanner on the VPS
```
git clone https://github.com/sudeep-sasikumar/BissBTCScanner /opt/BissBTCScanner
cd /opt/BissBTCScanner && python3 -m venv .venv && .venv/bin/pip install pandas numpy pyarrow requests pyyaml
sudo cp deploy/scanner.env.example /etc/biss-scanner.env && sudo chmod 600 /etc/biss-scanner.env   # bot token + chat id
sudo cp deploy/biss-scanner.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now biss-scanner
journalctl -u biss-scanner -f
```
- Test it once without Telegram: `python -m biss.scanner.live --once`. Without the env vars it prints alerts instead of sending them.
- What it scans is set in `config.yaml → scanner` (symbols, reclaim/entry variant, required filters, paper equity). It works once per closed 15m bar.
- Each alert has the level, sweep, reclaim, entry, stop %, TP1/TP2, R:R, risk tier, size, implied and WEEX max leverage, liquidation price vs stop, invalidation, filter results and the manual checklist. Open paper trades are followed to their exit and a close message is sent.
- Only tiers that passed section 8 belong in `scanner.symbols`; see the verdict in `reports/backtest.md`.
- Current profile (26 Nov 2026): R3w / E2 on T1 + T2 crypto (T1 list plus the top 50 WEEX crypto perps by
  24h volume, no TradeFi), longs and shorts. Sweep minimum 0.3 x ATR(4h), weekend sweeps skipped.
  Long filters: F2 drawdown, FOMC ±7 days, quarter close ±3 days, F4 location, stop ≤ 12%. Short filters: the
  same without F2. Risk 10% of paper equity x conviction (monthly level, or weekly level with F2 in band = 1.0x,
  otherwise 0.6x; shorts x0.5), total open risk ≤ 60%, no per-cluster cap, one position per coin per side,
  leverage caps 10x T1 / 5x T2, isolated margin. Paper equity follows closed paper trades.
- With the liquidation 1 stop-distance beyond the stop, margin is at least about 2.1x the risk, so at 10% risk
  free margin runs out after 4–5 full-size positions (about 45–50% open risk), before the 60% cap is reached.
  When margin is short the size is cut, never the stop widened.
