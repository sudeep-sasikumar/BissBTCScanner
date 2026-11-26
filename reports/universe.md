# WEEX USDT-M universe (section 3.1), pulled 25 Nov 2026

Source: `GET /capi/v3/market/exchangeInfo`, `/riskLimits`, `/ticker/24hr`, `/klines` (all verified live). Full per-contract table: `reports/universe_tiers.csv` (symbol, class, listing date, max leverage, brackets, tick, min size, maker/taker fee, funding interval, 30-day volume, Binance history symbol, tier).

## Contracts by class

|  | contracts | with_binance_history | median_vol_30d_m | pass_20m_floor | median_max_lev | taker_fee | maker_fee |
|---|---|---|---|---|---|---|---|
| commodity | 18 | 8 | 0.33 | 2 | 100 | 0.0008 | 0.0002 |
| crypto | 560 | 518 | 0.24 | 22 | 50 | 0.0008 | 0.0002 |
| fx | 7 | 1 | 0.05 | 0 | 100 | 0.0008 | 0.0002 |
| index | 45 | 26 | 0.25 | 1 | 20 | 0.0008 | 0.0002 |
| other | 4 | 3 | 0.03 | 0 | 20 | 0.0008 | 0.0002 |
| stock | 382 | 194 | 0.14 | 2 | 20 | 0.0008 | 0.0002 |

## Tiers today (WEEX 30-day volume)

|  | T1 | T2 | T4 | below floor |
|---|---|---|---|---|
| commodity | 0 | 0 | 2 | 16 |
| crypto | 5 | 45 | 0 | 510 |
| fx | 0 | 0 | 0 | 7 |
| index | 0 | 0 | 1 | 44 |
| other | 0 | 0 | 0 | 4 |
| stock | 0 | 0 | 2 | 380 |

## T1 and the 5 TradeFi contracts that pass the floor

|  | asset_class | listing_date | max_leverage | bracket1_cap_usd | bracket1_mmr | taker_fee | maker_fee | funding_interval_h | median_daily_vol_30d_usd | binance_symbol |
|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | crypto | 2019-12-31 | 400 | 2e+06 | 0.0015 | 0.0008 | 0.0002 | 8 | 3848.3 | BTCUSDT |
| ETHUSDT | crypto | 2019-12-31 | 400 | 1e+06 | 0.0015 | 0.0008 | 0.0002 | 8 | 2112.5 | ETHUSDT |
| SOLUSDT | crypto | 2023-10-25 | 300 | 2e+06 | 0.002 | 0.0008 | 0.0002 | 8 | 285.9 | SOLUSDT |
| ZECUSDT | crypto | 2024-07-03 | 100 | 100000 | 0.005 | 0.0008 | 0.0002 | 8 | 170.9 | ZECUSDT |
| HYPEUSDT | crypto | 2025-01-08 | 100 | 100000 | 0.005 | 0.0008 | 0.0002 | 4 | 26.6 | HYPEUSDT |
| BZUSDT | commodity | 2026-04-01 | 100 | 100000 | 0.005 | 0.0008 | 0.0002 | 4 | 433.6 | BZUSDT |
| XAUUSDT | commodity | 2026-07-28 | 100 | 100000 | 0.005 | 0.0008 | 0.0002 | 4 | 20.5 | XAUUSDT |
| SOXSUSDT | index | 2026-06-26 | 25 | 500000 | 0.02 | 0.0008 | 0.0002 | 8 | 48.2 | SOXSUSDT |
| GOOGLUSDT | stock | 2026-01-26 | 100 | 50000 | 0.005 | 0.0008 | 0.0002 | 8 | 671.1 | GOOGLUSDT |
| SKHYNIXUSDT | stock | 2026-06-02 | 50 | 100000 | 0.01 | 0.0008 | 0.0002 | 4 | 295.3 | SKHYNIXUSDT |

## History depth on WEEX (first bar served by historyKlines)

|  | weex_first_1w | weex_first_1d | weex_first_4h | weex_first_15m | weex_first_1m | binance_first_1d |
|---|---|---|---|---|---|---|
| BTCUSDT | 2019-12-30 | 2019-12-31 | 2019-12-31 | 2023-10-24 | 2023-10-24 | 2019-09-08 |
| ETHUSDT | 2019-12-30 | 2019-12-31 | 2019-12-31 | 2023-10-25 | 2023-10-25 | 2019-11-27 |
| SOLUSDT | 2023-10-23 | 2023-10-25 | 2023-10-25 | 2023-10-25 | 2023-10-25 | 2020-09-14 |
| HYPEUSDT | 2025-01-06 | 2025-01-08 | 2025-01-08 | 2025-01-08 | 2025-01-08 | 2025-05-30 |
| ZECUSDT | 2024-07-01 | 2024-07-03 | 2024-07-03 | 2024-07-03 | 2024-07-03 | 2020-02-05 |
| DOGEUSDT | 2023-10-23 | 2023-10-26 | 2023-10-26 | 2023-10-26 | 2023-10-26 | 2020-07-10 |
| XRPUSDT | 2023-11-20 | 2023-11-23 | 2023-11-23 | 2023-11-23 | 2023-11-23 | 2020-01-06 |
| LINKUSDT | 2023-10-23 | 2023-10-26 | 2023-10-26 | 2023-10-26 | 2023-10-26 | 2020-01-17 |
| AAPLUSDT | 2026-01-12 | 2026-01-14 | 2026-01-14 | 2026-01-14 | 2026-01-14 | 2026-04-06 |
| NVDAUSDT | 2026-01-12 | 2026-01-14 | 2026-01-14 | 2026-01-14 | 2026-01-14 | 2026-03-26 |
| TSLAUSDT | 2026-01-19 | 2026-01-21 | 2026-01-21 | 2026-01-21 | 2026-01-21 | 2026-01-28 |
| SPYUSDT | 2026-01-26 | 2026-01-28 | 2026-01-28 | 2026-01-28 | 2026-01-28 | 2026-04-06 |
| QQQUSDT | 2026-01-26 | 2026-01-28 | 2026-01-28 | 2026-01-28 | 2026-01-28 | 2026-04-06 |
| XAUUSDT | 2026-07-27 | 2026-07-28 | 2026-07-28 | 2026-07-28 | 2026-07-28 | 2025-12-11 |
| CLUSDT | 2026-03-30 | 2026-04-01 | 2026-04-01 | 2026-04-01 | 2026-04-01 | 2026-04-01 |
| EURUSDT | 2025-04-07 | 2025-04-07 | 2025-04-07 | 2025-04-07 | 2025-04-07 |  |
| SP500USDT | 2026-01-29 | 2026-01-29 | 2026-01-29 | 2026-01-29 | 2026-06-26 |  |
| NAS100USDT | 2026-08-03 | 2026-08-06 | 2026-08-06 | 2026-08-06 | 2026-08-06 |  |
| MSTRUSDT | 2026-01-12 | 2026-01-15 | 2026-01-15 | 2026-01-15 | 2026-01-15 | 2026-02-09 |
| COINUSDT | 2026-01-12 | 2026-01-14 | 2026-01-14 | 2026-01-14 | 2026-01-14 | 2026-02-09 |

WEEX has no 1M interval (allowed: 1m..1w); monthly bars are built from daily. WEEX 15m/1m starts Oct 2023 even for BTC/ETH, most alts Oct 2023 or later, TradeFi Jan 2026 or later -> the backtest uses Binance USDT-M history (data.binance.vision, delisted contracts included) for crypto, mapped by base asset. 42 WEEX crypto contracts have no Binance history and are not testable.

## TradeFi when the underlying market is closed (WEEX 1h bars, last 40 days)

|  | hours | weekend_bars | weekend_flat_pct | weekend_med_range_pct | weekend_med_qvol | us_session_med_range_pct | us_session_med_qvol | weekday_offhours_med_range_pct | weekday_offhours_med_qvol | max_gap_mon_open_pct |
|---|---|---|---|---|---|---|---|---|---|---|
| GOOGLUSDT | 961 | 288 | 0 | 0.183 | 3.78423e+06 | 0.737 | 2.81517e+07 | 0.471 | 1.31765e+07 | 2.85 |
| BZUSDT | 961 | 288 | 0 | 0.174 | 544262 | 0.804 | 2.91738e+07 | 0.595 | 1.67648e+07 | 4.35 |
| SKHYNIXUSDT | 961 | 288 | 0 | 0.485 | 899071 | 1.41 | 9.05156e+06 | 1.38 | 9.50081e+06 | 6.76 |
| SOXSUSDT | 961 | 288 | 0 | 0.905 | 1.62377e+06 | 3.745 | 1.9142e+06 | 2.529 | 1.84842e+06 | 9.85 |
| XAUUSDT | 961 | 288 | 0 | 0.086 | 155605 | 0.353 | 534302 | 0.336 | 408938 | 2.11 |
| XAUTUSDT | 961 | 288 | 0 | 0.082 | 156770 | 0.344 | 433162 | 0.331 | 435550 | 2.05 |
| SOXLUSDT | 961 | 288 | 0 | 0.91 | 458201 | 4.024 | 727202 | 2.511 | 613348 | 9.72 |
| MUUSDT | 961 | 288 | 0 | 0.46 | 205795 | 1.662 | 355875 | 1.063 | 308879 | 3.89 |
| SNDKUSDT | 961 | 288 | 0 | 0.497 | 103076 | 1.985 | 697444 | 1.38 | 237069 | 4.81 |
| SKHYUSDT | 961 | 288 | 0 | 0.436 | 329385 | 1.523 | 518807 | 1.227 | 497753 | 4.91 |
| XAGUSDT | 961 | 288 | 0 | 0.187 | 192817 | 0.691 | 297838 | 0.629 | 255930 | 2.43 |
| NVDAUSDT | 961 | 288 | 0 | 0.231 | 43171 | 1.151 | 103515 | 0.726 | 82829 | 5.78 |
| QQQUSDT | 961 | 288 | 0 | 0.129 | 140409 | 0.621 | 254779 | 0.353 | 229682 | 1.85 |
| PAXGUSDT | 961 | 288 | 0 | 0.082 | 149811 | 0.349 | 177956 | 0.329 | 198956 | 2.01 |
| INTCUSDT | 961 | 288 | 0 | 0.436 | 132946 | 1.692 | 256959 | 1.111 | 206145 | 4.83 |
| SPYUSDT | 961 | 288 | 0 | 0.081 | 109881 | 0.385 | 247888 | 0.198 | 194352 | 1.34 |
| LITEUSDT | 961 | 288 | 0 | 0.35 | 106525 | 2.053 | 211648 | 1.357 | 191448 | 4.79 |
| OPENAIUSDT | 961 | 288 | 0 | 0.428 | 107118 | 0.746 | 172030 | 0.576 | 143685 | 5.01 |
| AMDUSDT | 961 | 288 | 0 | 0.365 | 72140 | 1.688 | 184618 | 1.09 | 159026 | 4.83 |
| UNITREEUSDT | 961 | 288 | 0 | 0.332 | 58589 | 0.583 | 128165 | 0.791 | 180326 | 20.82 |
| CEGUSDT | 961 | 288 | 19.8 | 0.1 | 90 | 0.93 | 219 | 0.36 | 164 | 3.16 |
| DRAMUSDT | 961 | 288 | 0 | 0.401 | 91778 | 1.375 | 148657 | 1.119 | 140305 | 4.94 |
| METAUSDT | 961 | 288 | 0 | 0.136 | 59269 | 0.884 | 189226 | 0.446 | 119900 | 2.3 |
| ASMLUSDT | 961 | 288 | 0 | 0.235 | 62399 | 0.989 | 143955 | 0.774 | 127146 | 3.68 |
| TSLAUSDT | 961 | 288 | 0 | 0.174 | 54724 | 0.97 | 145762 | 0.511 | 109714 | 2.9 |
| BTCUSDT | 961 | 288 | 0 | 0.33 | 4.35048e+07 | 0.723 | 1.75637e+08 | 0.551 | 8.70295e+07 | 6.07 |

Finding: WEEX TradeFi perps trade 24/7 on their own book (no frozen or flat bars on weekends, except near-dead CEG). Weekend ranges are about 1/4 of the US cash session and volume about 1/5-1/10, and the move from the Friday close to the Monday US open reached 2-10%. So a weekend 'sweep' happens on thin volume, and a stop can be jumped at the Monday open. The backtest fills such stops at the first price beyond the stop (bar open).
