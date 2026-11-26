# Build status (26 Nov 2026)

Every part of BUILD_PROMPT.md section 9 has been built:
- **A. Universe report:** `reports/universe.md` and `reports/universe_tiers.csv`.
- **B. Backtest reports:** `reports/backtest.md` (full grid, baselines, management, ablation, shorts, level types, years, frequency, account sims, leverage, mark price, reference cases), `reports/final.md` (the rule set left after the section 8 protocol) and `reports/tradfi.md`.
- **C. Paper scanner:** `biss/scanner/` plus `deploy/` (systemd unit and env template). It needs `BISS_TG_TOKEN` and `BISS_TG_CHAT`.
- **D. Trade journal:** `reports/journal.csv`, for the final rule set at 3% risk.

## Open items
- F6 (open interest and liquidations at the sweep) is not implemented; see docs/ASSUMPTIONS.md.
- The 2027 FOMC dates are tentative. Check them before live use.
- Pushing to GitHub is waiting for your OK. The Telegram bot token is yours to add on the VPS.
- The refined-baseline reproduction gives +0.48R against the documented +0.97R. Trade counts, years and hold times match; the average R gap is unexplained.
