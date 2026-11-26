# Final rule set (after the section 8 protocol)

Variant chosen on the in-sample slice only: **R3w/E2** (weekly close back above the swept HTF level, then the first 15m pullback that holds the level). Filters kept (removing each lowered avg R in IS, OOS and holdout): **F2_drawdown, F3_fomc, F3_qclose, F4_location, stop_max**. Dropped: F1_regime, min_rr.

## Final vs baselines

Documented refined result: 158 trades, 68% win, +0.97R. Rule C: about 0R (reproduced: -0.09 to -0.01R, reports/backtest.md section 2).

|  | trades | win% | loss% | scratch% | avgR | medR | PF | maxLossStreak | maxDD_R | medHold_d | avg_stop% | avg_lev_need | at_cap% | funding_R | fees_R_avg | avgR_ex_top10 | top10_share% | IS_n | IS_avgR | OOS_n | OOS_avgR | HO_n | HO_avgR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FINAL T1+T2, 50%@1R+BE | 233 | 60.5 | 39.5 | 0 | 0.438 | 0.433 | 2.04 | 14 | 30.6 | 8.8 | 7.64 | 6.9 | 75.1 | 5.46 | 0.033 | 0.181 | 60 | 105 | 0.465 | 60 | 0.558 | 68 | 0.289 |
| FINAL T1+T2, 50%@TP1+BE | 228 | 49.1 | 50.9 | 0 | 0.526 | -0.99 | 1.97 | 22 | 33.5 | 11 | 7.67 | 6.9 | 74.6 | 7.29 | 0.034 | 0.227 | 59 | 102 | 0.534 | 58 | 0.632 | 68 | 0.424 |
| FINAL T1 only | 26 | 84.6 | 15.4 | 0 | 1.043 | 0.465 | 7.48 | 2 | 2.1 | 20.5 | 7.32 | 7.5 | 57.7 | 0.97 | 0.023 | 0.071 | 96 | 15 | 1.001 | 11 | 1.1 | 0 |  |
| FINAL T2 only | 208 | 57.2 | 42.8 | 0 | 0.355 | 0.423 | 1.78 | 14 | 31.9 | 7.7 | 7.68 | 6.8 | 77.9 | 4.47 | 0.035 | 0.069 | 81 | 91 | 0.377 | 49 | 0.406 | 68 | 0.29 |
| FINAL T3 | 279 | 54.5 | 44.8 | 0.7 | -0.066 | 0.327 | 0.87 | 20 | 48.4 | 7.4 | 7.87 | 6.4 | 65.6 | 7.6 | 0.062 | -0.227 |  | 119 | -0.127 | 61 | -0.063 | 99 | 0.004 |
| FINAL T4 (5 liquid TradeFi) | 4 | 50 | 50 | 0 | -0.315 | -0.34 | 0.44 | 1 | 1.7 | 7.6 | 5.31 | 9.6 | 100 | 0.08 | 0.049 | 0 |  | 0 |  | 1 | 0.427 | 3 | -0.563 |
| FINAL T4 pool (other TradeFi) | 88 | 46.6 | 53.4 | 0 | -0.152 | -1.033 | 0.73 | 8 | 20 | 5.5 | 5.97 | 8.6 | 100 | 1.79 | 0.046 | -0.398 |  | 1 | 1.055 | 55 | -0.19 | 32 | -0.125 |
| same, all 7 filters (pre-protocol), T1+T2 | 134 | 70.1 | 29.9 | 0 | 0.82 | 0.454 | 3.59 | 5 | 7.4 | 11.5 | 7.72 | 7 | 69.4 | 3.22 | 0.033 | 0.401 | 55 | 62 | 1.068 | 31 | 0.392 | 41 | 0.77 |
| 15m R1/E1 with final filters, T1+T2 | 1345 | 47 | 52.6 | 0.4 | -0.028 | -1.037 | 0.95 | 23 | 185.6 | 1.3 | 4.25 | 13.2 | 95.5 | 18.22 | 0.068 | -0.143 |  | 491 | 0.067 | 474 | -0.124 | 380 | -0.03 |
| 4h R2/E1 with final filters, T1+T2 | 1163 | 47.1 | 52 | 0.9 | 0.036 | -1.031 | 1.06 | 20 | 134.6 | 1.8 | 4.71 | 12 | 93.6 | 16.64 | 0.061 | -0.087 | 339 | 435 | 0.109 | 401 | -0.091 | 327 | 0.095 |
| BASELINE refined weekly (WEEX costs, my reproduction) | 186 | 63.4 | 36.6 | 0 | 0.483 | 0.483 | 2.32 | 9 | 9.8 | 14.5 | 12.46 |  |  | 0 | 0.016 | 0.151 | 70 | 63 | 0.845 | 71 | 0.268 | 52 | 0.336 |


## Ablation of the final set (T1+T2)

|  | trades | win% | loss% | scratch% | avgR | medR | PF | maxLossStreak | maxDD_R | medHold_d | avg_stop% | avg_lev_need | at_cap% | funding_R | fees_R_avg | avgR_ex_top10 | top10_share% | IS_n | IS_avgR | OOS_n | OOS_avgR | HO_n | HO_avgR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| final | 233 | 60.5 | 39.5 | 0 | 0.438 | 0.433 | 2.04 | 14 | 30.6 | 8.8 | 7.64 | 6.9 | 75.1 | 5.46 | 0.033 | 0.181 | 60 | 105 | 0.465 | 60 | 0.558 | 68 | 0.289 |
| without F2_drawdown | 520 | 60.8 | 39.2 | 0 | 0.307 | 0.435 | 1.75 | 17 | 41.7 | 7.9 | 8.21 | 6.4 | 63.8 | 9.46 | 0.031 | 0.154 | 51 | 225 | 0.441 | 156 | 0.242 | 139 | 0.164 |
| without F3_fomc | 313 | 52.7 | 47.3 | 0 | 0.218 | 0.365 | 1.44 | 13 | 25.8 | 7.8 | 7.7 | 6.9 | 75.4 | 7.5 | 0.034 | 0.022 | 90 | 134 | 0.289 | 89 | 0.099 | 90 | 0.231 |
| without F3_qclose | 266 | 58.6 | 41.4 | 0 | 0.329 | 0.427 | 1.75 | 18 | 28.9 | 8.5 | 7.71 | 6.8 | 74.1 | 5.76 | 0.033 | 0.102 | 70 | 121 | 0.343 | 71 | 0.444 | 74 | 0.194 |
| without F4_location | 512 | 55.9 | 44.1 | 0 | 0.141 | 0.413 | 1.3 | 16 | 59.8 | 7 | 8.03 | 6.6 | 69.3 | 8.49 | 0.032 | 0.017 | 88 | 212 | 0.094 | 154 | 0.207 | 146 | 0.138 |
| without stop_max | 361 | 58.4 | 41.6 | 0 | 0.286 | 0.428 | 1.66 | 12 | 32.5 | 11.6 | 12.17 | 5.2 | 45.4 | 7.6 | 0.025 | 0.118 | 60 | 159 | 0.362 | 101 | 0.267 | 101 | 0.185 |
| plus F1_regime | 134 | 70.1 | 29.9 | 0 | 0.82 | 0.454 | 3.59 | 5 | 7.4 | 11.5 | 7.72 | 7 | 69.4 | 3.22 | 0.033 | 0.401 | 55 | 62 | 1.068 | 31 | 0.392 | 41 | 0.77 |
| plus min_rr | 233 | 60.5 | 39.5 | 0 | 0.438 | 0.433 | 2.04 | 14 | 30.6 | 8.8 | 7.64 | 6.9 | 75.1 | 5.46 | 0.033 | 0.181 | 60 | 105 | 0.465 | 60 | 0.558 | 68 | 0.289 |


## Final set by level type

|  | trades | win% | loss% | scratch% | avgR | medR | PF | maxLossStreak | maxDD_R | medHold_d | avg_stop% | avg_lev_need | at_cap% | funding_R | fees_R_avg | avgR_ex_top10 | top10_share% | IS_n | IS_avgR | OOS_n | OOS_avgR | HO_n | HO_avgR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| monthly | 6 | 50 | 50 | 0 | -0.297 | -0.301 | 0.43 | 1 | 2.2 | 5.2 | 8.27 | 6.4 | 66.7 | 0.04 | 0.032 | 0 |  | 2 | -0.301 | 2 | -0.292 | 2 | -0.299 |
| open | 72 | 47.2 | 52.8 | 0 | -0.04 | -1.028 | 0.93 | 12 | 18.4 | 7.5 | 7.5 | 7.1 | 77.8 | 1.35 | 0.035 | -0.48 |  | 31 | -0.023 | 20 | 0.263 | 21 | -0.354 |
| range | 90 | 67.8 | 32.2 | 0 | 0.797 | 0.44 | 3.31 | 6 | 10 | 11.6 | 7.48 | 7 | 78.9 | 3.08 | 0.033 | 0.2 | 78 | 47 | 0.939 | 17 | 0.089 | 26 | 1.005 |
| weekly | 65 | 66.2 | 33.8 | 0 | 0.536 | 0.442 | 2.5 | 4 | 5.4 | 10.1 | 7.96 | 6.6 | 67.7 | 0.99 | 0.031 | -0.122 | 119 | 25 | 0.239 | 21 | 1.301 | 19 | 0.082 |

## Final set by year

|  | trades | win% | loss% | scratch% | avgR | medR | PF | maxLossStreak | maxDD_R | medHold_d | avg_stop% | avg_lev_need | at_cap% | funding_R | fees_R_avg | avgR_ex_top10 | top10_share% | IS_n | IS_avgR | OOS_n | OOS_avgR | HO_n | HO_avgR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 34 | 70.6 | 29.4 | 0 | 0.68 | 0.464 | 3.16 | 4 | 4.3 | 14.9 | 8 | 6.8 | 58.8 | 0.58 | 0.032 | -0.178 | 118 | 24 | 1.028 | 0 |  | 10 | -0.156 |
| 2023 | 84 | 50 | 50 | 0 | 0.456 | -0.326 | 1.86 | 13 | 30.6 | 7.5 | 7.33 | 7 | 83.3 | 2.39 | 0.035 | -0.211 | 141 | 53 | 0.289 | 0 |  | 31 | 0.743 |
| 2024 | 45 | 60 | 40 | 0 | 0.176 | 0.438 | 1.41 | 4 | 8.8 | 9.6 | 8.53 | 6 | 64.4 | 1.32 | 0.029 | -0.336 | 248 | 28 | 0.316 | 3 | 0.457 | 14 | -0.163 |
| 2025 | 40 | 80 | 20 | 0 | 0.616 | 0.446 | 3.95 | 3 | 3.4 | 11.6 | 7.9 | 6.5 | 77.5 | 0.78 | 0.03 | 0.042 | 95 | 0 |  | 33 | 0.746 | 7 | 0.006 |
| 2026 | 30 | 53.3 | 46.7 | 0 | 0.266 | 0.427 | 1.53 | 4 | 5.6 | 6.4 | 6.43 | 8.8 | 83.3 | 0.39 | 0.041 | -0.621 | 256 | 0 |  | 24 | 0.313 | 6 | 0.075 |


Top-10 trades: 61.6R of 102.0R total; avg R without them 0.18.


|  | entry_time | level | level_type | R |
|---|---|---|---|---|
| 1000SHIBUSDT | 2023-01-02 01:30:00+00:00 | 0.007888 | range | 8.7029 |
| MTLUSDT | 2023-01-09 00:45:00+00:00 | 0.692 | open | 6.70058 |
| ENAUSDT | 2025-07-07 02:15:00+00:00 | 0.2561 | weekly | 6.21696 |
| ETHUSDT | 2026-06-29 01:00:00+00:00 | 1528.61 | weekly | 6.20059 |
| APTUSDT | 2023-10-16 01:30:00+00:00 | 4.853 | range | 6.06611 |
| XRPUSDT | 2023-01-09 01:00:00+00:00 | 0.3334 | range | 5.80958 |
| BTCUSDT | 2022-11-28 03:15:00+00:00 | 15805.5 | range | 5.5921 |
| ADAUSDT | 2025-07-07 01:30:00+00:00 | 0.5797 | weekly | 5.51561 |
| MATICUSDT | 2022-12-26 01:45:00+00:00 | 0.7805 | range | 5.4893 |
| ARKUSDT | 2023-10-23 01:30:00+00:00 | 0.4427 | range | 5.33262 |


## $1,000 account, 300 random within-week orderings (mode a unless stated)

|  | median_end | p10_end | median_dd | p90_dd | median_taken |
|---|---|---|---|---|---|
| T1 @ 2% | 1413.64 | 1413.64 | 0.03 | 0.03 | 26 |
| T1 @ 3% | 1655.56 | 1655.56 | 0.05 | 0.05 | 26 |
| T1 @ 4% | 1922.55 | 1922.55 | 0.07 | 0.07 | 26 |
| T1 @ 5% | 2215.85 | 2215.85 | 0.08 | 0.08 | 26 |
| T2 @ 2% | 1425.31 | 1277.46 | 0.16 | 0.19 | 114 |
| T2 @ 3% | 1642.3 | 1401.38 | 0.23 | 0.27 | 114 |
| T2 @ 4% | 1853.66 | 1508.47 | 0.29 | 0.34 | 114 |
| T2 @ 5% | 2047.5 | 1596.59 | 0.35 | 0.41 | 114 |
| T1+T2 @ 2% | 1931.17 | 1751.4 | 0.15 | 0.19 | 129 |
| T1+T2 @ 3% | 2528.86 | 2200.5 | 0.22 | 0.27 | 129 |
| T1+T2 @ 4% | 3207.71 | 2666.09 | 0.28 | 0.35 | 129 |
| T1+T2 @ 5% | 3801.44 | 3103.38 | 0.34 | 0.42 | 129 |
| mode (b) T1+T2 @ 20% | 2340.55 | 862.66 | 0.55 | 0.72 | 47 |
| mode (b) T1+T2 @ 35% | 1897.02 | 370.36 | 0.78 | 0.91 | 47 |
| mode (b) T1+T2 @ 50% | 1016.14 | 99.09 | 0.9 | 0.98 | 47 |


Journal (`reports/journal.csv`): 3% risk, chronological: 124 taken, skipped {'cluster_cap': 109}, sized at a leverage cap 87, shrunk for margin 0, avg leverage 5.1x (max 10.0x), $1,000 -> $2,471, max DD 20%. Leverage needed for the 1x-stop liquidation buffer: median 6.3x; 75% of trades needed more than the cap (sized down, never a wider stop).

## Reference cases (section 8.7)

| Case | Variant | Detected? | Entry | Stop | Filters failed (final set) | R |
|---|---|---|---|---|---|---|
| BTC weekly ~58.9k, swept 30 Jun 2026, reclaimed 1 Jul | R1/E1 | yes (L=59800, swept 58850 29 Jun 02:00) | 29 Jun 03:30 @ 60151.7 | 58261.5 (3.1%) | F2_drawdown, F3_qclose [tier T1] | -1.07 |
| BTC weekly ~58.9k, swept 30 Jun 2026, reclaimed 1 Jul | R2/E1 | yes (L=59800, swept 58850 29 Jun 02:00) | 29 Jun 04:00 @ 60019.8 | 58261.5 (2.9%) | F2_drawdown, F3_qclose [tier T1] | -1.08 |
| BTC weekly ~58.9k, swept 30 Jun 2026, reclaimed 1 Jul | R3d/E1 | yes (L=59800, swept 58850 29 Jun 02:00) | 30 Jun 00:00 @ 60224.7 | 58261.5 (3.3%) | F2_drawdown, F3_qclose [tier T1] | -1.06 |
| BTC weekly ~58.9k, swept 30 Jun 2026, reclaimed 1 Jul | R3w/E1 | yes (L=59800, swept 57758.6 01 Jul 01:00) | 06 Jul 00:00 @ 63617.1 | 57181 (10.1%) | F3_qclose [tier T1] | 1.87 |
| HYPE ~52.64, swept 31 Jul 2026, reclaimed 3 Aug | R1/E1 | yes (L=52.636, swept 51.823 31 Jul 20:00) | 31 Jul 20:45 @ 52.909 | 51.3048 (3.0%) | F3_fomc [tier T1] | -1.08 |
| HYPE ~52.64, swept 31 Jul 2026, reclaimed 3 Aug | R2/E1 | yes (L=52.636, swept 51.908 03 Aug 06:30) | 03 Aug 12:00 @ 52.75 | 51.3889 (2.6%) | F3_fomc [tier T1] | 9.28 |
| HYPE ~52.64, swept 31 Jul 2026, reclaimed 3 Aug | R3d/E1 | yes (L=52.559, swept 51.908 03 Aug 06:30) | 04 Aug 00:00 @ 53.999 | 51.3889 (4.8%) | F3_fomc [tier T1] | 0.45 |
| HYPE ~52.64, swept 31 Jul 2026, reclaimed 3 Aug | R3w/E1 | yes (L=52.559, swept 51.908 03 Aug 06:30) | 10 Aug 00:00 @ 53.857 | 51.3889 (4.6%) | none - TRADE [tier T1] | 5.13 |
| ZEC ~300.8, swept 5 Jun 2026 | R1/E1 | yes (L=300.78, swept 250 05 Jun 07:00) | 05 Jun 07:45 @ 310.94 | 237.256 (23.7%) | F2_drawdown, stop_max [tier T1] | 3.07 |
| ZEC ~300.8, swept 5 Jun 2026 | R2/E1 | yes (L=300.78, swept 250 05 Jun 07:00) | 05 Jun 08:00 @ 308.64 | 237.256 (23.1%) | F2_drawdown, stop_max [tier T1] | 3.17 |
| ZEC ~300.8, swept 5 Jun 2026 | R3d/E1 | yes (L=300.78, swept 250 05 Jun 07:00) | 06 Jun 00:00 @ 388.88 | 234.201 (39.8%) | F2_drawdown, stop_max [tier T1] | 0.53 |
| ZEC ~300.8, swept 5 Jun 2026 | R3w/E1 | yes (L=300.78, swept 250 05 Jun 07:00) | 08 Jun 00:00 @ 440.03 | 237.627 (46.0%) | F2_drawdown, stop_max [tier T1] | 1.12 |
| BTC below the lows, back above ~61.5k (17-20 Nov 2026) | R1/E1 | yes (L=62401.7, swept 62030.8 18 Nov 22:45) | 18 Nov 23:30 @ 62750.4 | 61410.5 (2.1%) | F2_drawdown [tier T1] | -1.10 |
| BTC below the lows, back above ~61.5k (17-20 Nov 2026) | R2/E1 | yes (L=62401.7, swept 62030.8 18 Nov 22:45) | 19 Nov 00:00 @ 63036.8 | 61410.5 (2.6%) | F2_drawdown [tier T1] | -1.08 |
| BTC below the lows, back above ~61.5k (17-20 Nov 2026) | R3d/E1 | yes (L=62401.7, swept 62030.8 18 Nov 22:45) | 19 Nov 00:00 @ 63036.8 | 61410.5 (2.6%) | F2_drawdown [tier T1] | -1.08 |
| BTC below the lows, back above ~61.5k (17-20 Nov 2026) | R3w/E1 | no | | | no R3w reclaim of a level within 2%; levels swept then: 56537.7, 57758.6, 58900, 61950, 62401.7, 64918.2 | |
| BTC 57.3-57.7k higher-low plan (23 Nov 2026) | R1/E1 | yes (L=57758.6, swept 57256.5 25 Nov 14:45) | 25 Nov 15:15 @ 57975.8 | 56683.9 (2.2%) | none - TRADE [tier T1] | 1.29 |
| BTC 57.3-57.7k higher-low plan (23 Nov 2026) | R2/E1 | yes (L=57758.6, swept 57256.5 25 Nov 14:45) | 25 Nov 16:00 @ 58314 | 56683.9 (2.8%) | none - TRADE [tier T1] | 1.03 |
| BTC 57.3-57.7k higher-low plan (23 Nov 2026) | R3d/E1 | no | | | no R3d reclaim of a level within 2%; levels swept then: 57758.6, 58900, 59800 | |
| BTC 57.3-57.7k higher-low plan (23 Nov 2026) | R3w/E1 | no | | | no R3w reclaim of a level within 2%; levels swept then: 57758.6, 58900, 59800 | |
