# Strategy backtest (main, 200 orderings)

Scanner profile in config.yaml: R3w/E2, tiers ['T1', 'T2'], filters {'long': ['F2_drawdown', 'F3_fomc', 'F3_qclose', 'F4_location', 'stop_max'], 'short': ['F1_bull', 'F3_fomc', 'F3_qclose', 'F4_location', 'stop_max']}, risk 10% x conviction, open-risk cap 60%, cluster cap None.

Signals 389 (233 long, 156 short), 2022-10-10 to 2026-11-09.

$1,000 start: median end $45,695, worst 10% $27,160, best 10% $69,379; median max drawdown 56% (worst 10% 60%); median trades taken 304.

Median route: end $45,884, max drawdown 56%, taken 302, skipped {'no_margin': 87}, Sharpe 1.52, Sortino 3.60, CAGR 145%.

## Per side and tier

|  | trades | win% | loss% | scratch% | avgR | medR | PF | sumR | maxLossStreak | maxDD_R | medHold_d | exposure | avg_stop% | avgR_ex_top10 | top10_share% | funding_R | fees_R_avg | avg_lev_need | max_lev_need | at_cap% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| long T1 | 26 | 88.5 | 11.5 | 0 | 1.101 | 0.467 | 10.13 | 28.6 | 1 | 1.1 | 20.5 | 0.48 | 7.51 | 0.166 | 91 | 0.98 | 0.022 | 7.3 | 17.6 | 11.5 |
| long T2 | 207 | 57 | 43 | 0 | 0.354 | 0.423 | 1.77 | 73.3 | 14 | 31.9 | 7.6 | 2.03 | 7.66 | 0.067 | 82 | 4.49 | 0.035 | 6.9 | 16.2 | 77.8 |
| short T1 | 37 | 51.4 | 48.6 | 0 | 0.062 | 0.427 | 1.13 | 2.3 | 5 | 7.4 | 8.9 | 0.51 | 6.93 | -0.504 | 695 | -1.63 | 0.027 | 8.2 | 17.9 | 27 |
| short T2 | 119 | 61.3 | 38.7 | 0 | 0.37 | 0.474 | 1.93 | 44 | 4 | 8.8 | 6.9 | 2.07 | 8.48 | 0.03 | 93 | -2.36 | 0.03 | 6.2 | 15.7 | 66.4 |