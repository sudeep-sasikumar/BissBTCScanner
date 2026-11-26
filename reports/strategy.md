# Strategy backtest (main, 200 orderings)

Scanner profile in config.yaml: R3w/E2, tiers ['T1', 'T2'], filters {'long': ['F2_drawdown', 'F3_fomc', 'F3_qclose', 'F4_location', 'stop_max'], 'short': ['F3_fomc', 'F3_qclose', 'F4_location', 'stop_max']}, risk 10% x conviction, open-risk cap 60%, cluster cap None.

Signals 462 (233 long, 229 short), 2022-10-10 to 2026-11-09.

$1,000 start: median end $26,011, worst 10% $16,882, best 10% $42,807; median max drawdown 57% (worst 10% 61%); median trades taken 358.

Median route: end $26,021, max drawdown 59%, taken 367, skipped {'no_margin': 95}, Sharpe 1.20, Sortino 3.45, CAGR 120%.

## Per side and tier

|  | trades | win% | loss% | scratch% | avgR | medR | PF | sumR | maxLossStreak | maxDD_R | medHold_d | exposure | avg_stop% | avgR_ex_top10 | top10_share% | funding_R | fees_R_avg | avg_lev_need | max_lev_need | at_cap% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long T1 | 26 | 88.5 | 11.5 | 0 | 1.101 | 0.467 | 10.13 | 28.6 | 1 | 1.1 | 20.5 | 0.48 | 7.51 | 0.166 | 91 | 0.98 | 0.022 | 7.3 | 17.6 | 11.5 |
| long T2 | 207 | 57 | 43 | 0 | 0.354 | 0.423 | 1.77 | 73.3 | 14 | 31.9 | 7.6 | 2.03 | 7.66 | 0.067 | 82 | 4.49 | 0.035 | 6.9 | 16.2 | 77.8 |
| short T1 | 54 | 46.3 | 53.7 | 0 | -0.061 | -0.949 | 0.89 | -3.3 | 6 | 11.3 | 9 | 0.66 | 6.9 | -0.496 |  | -1.95 | 0.028 | 8.5 | 17.9 | 31.5 |
| short T2 | 175 | 53.7 | 46.3 | 0 | 0.142 | 0.44 | 1.3 | 24.9 | 6 | 16.8 | 6.8 | 2.5 | 8.41 | -0.099 | 165 | -3.24 | 0.031 | 6.3 | 15.7 | 67.4 |