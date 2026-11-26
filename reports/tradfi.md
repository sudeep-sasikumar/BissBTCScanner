# TradeFi study (T4 and wider pool) - reported separately from crypto

Pool: 58 WEEX TradFi contracts with >= $1M median daily volume; 5 pass the $20M floor (T4: BZUSDT, XAUUSDT, SOXSUSDT, GOOGLUSDT, SKHYNIXUSDT). Underlying daily history from Yahoo Finance; 47 with enough history.

Engine: daily sweep of a validated weekly level, daily close back above within 14 days, entry at that close, stop 1% below the swept low, 50% at +1R then stop to entry, rest to the 120-day high. Gaps through the stop fill at the open. Costs: 0.08% taker / 0.02% maker, 0.1% slippage, assumed funding 0.01%/8h.

|  | trades | win% | loss% | avgR | medR | PF | maxLossStreak | medHold_d | IS_n | IS_avgR | OOS_n | OOS_avgR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all sweeps (no filters) | 3296 | 49.3 | 49.2 | 0.014 | 0.023 | 1.02 | 31 | 6 | 1610 | -0.009 | 1686 | 0.035 |
| F2 drawdown 10-30% | 970 | 46.5 | 52 | -0.094 | -0.316 | 0.84 | 10 | 7 | 473 | -0.094 | 497 | -0.095 |
| F2 + no FOMC +-7d | 660 | 45.9 | 52.6 | -0.128 | -0.377 | 0.79 | 8 | 7 | 316 | -0.145 | 344 | -0.112 |
| F2 + FOMC + no earnings +-2 sessions | 621 | 45.9 | 52.7 | -0.135 | -0.359 | 0.77 | 7 | 7 | 297 | -0.119 | 324 | -0.149 |
|   ... + S&P not bull | 177 | 46.9 | 52 | -0.119 | -0.395 | 0.8 | 6 | 7 | 85 | -0.175 | 92 | -0.066 |
|   ... + S&P bull only | 444 | 45.5 | 52.9 | -0.141 | -0.341 | 0.76 | 9 | 7 | 212 | -0.096 | 232 | -0.182 |
|   ... + stop<=12% | 573 | 44.9 | 53.8 | -0.153 | -0.573 | 0.75 | 8 | 7 | 276 | -0.126 | 297 | -0.179 |
| level move 10% instead of 20%, F2+FOMC+earn | 695 | 45.5 | 52.1 | -0.153 | -0.359 | 0.74 | 9 | 7 | 332 | -0.143 | 363 | -0.163 |
| class commodity (F2+FOMC+earn) | 100 | 45 | 53 | -0.116 | -0.346 | 0.8 | 6 | 8.5 | 40 | -0.192 | 60 | -0.066 |
| class index (F2+FOMC+earn) | 66 | 40.9 | 56.1 | -0.274 | -1.028 | 0.57 | 11 | 5 | 36 | -0.416 | 30 | -0.104 |
| class stock (F2+FOMC+earn) | 455 | 46.8 | 52.1 | -0.118 | -0.322 | 0.8 | 8 | 7 | 221 | -0.057 | 234 | -0.177 |
| T4 contracts only (>= $20M/day) | 54 | 40.7 | 57.4 | -0.223 | -1.035 | 0.66 | 6 | 6 | 18 | -0.265 | 36 | -0.202 |

