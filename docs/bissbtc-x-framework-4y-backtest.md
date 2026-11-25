# BissBTC X-post framework: 4-year backtest, $1,000 start (28 Oct 2022 – 28 Oct 2026)

**Rules:** same as `bissbtc-x-framework-all-trades-1000.md` (weekly support, 30–65% drawdown from the 120-day high, daily sweep and reclaim within 14 days, stop 1% under the swept low, target the previous high, one signal per coin per 30 days). Weekly levels now use each coin's full Binance perp history (from 2019), so the last 6 months show 75 signals instead of 71.
**Universe:** the 32 coins in today's CoinGecko top 50 that have a Binance USDT perp. A coin trades only once it has 30 weeks of history (HYPE from 2025, GRAM/BTW never).
**Sizing:** every signal taken; margin = **4% of the closed balance** at entry (peak was 22 open trades, so every trade was fully funded). Leverage: cap 10x for BTC/ETH/HYPE/SOL, 5x for others, cut to floor(50% ÷ stop%). Fees 0.05% per side; no funding or slippage.
**Full trade list:** `bissbtc-x-framework-4y-trades.csv` (588 rows; not included in this pack; columns: coin, entry_date, entry, stop, stop_pct, target, leverage, margin_usd, result, exit_date, exit_price, trade_return_pct, pnl_usd, closed_balance_after).

## Result
- $1,000 → **$2,281.89** (+128%, about 23% a year): $1,960.35 closed + $321.54 on 6 open trades.
- 588 trades: 91 targets (15.5%), 491 stops, 6 open. Average winner +243% on margin, average loser −31%.
- Max drawdown −74%: closed balance $2,499.68 (16 Dec 2024) → $656 (5 Apr 2026).
- Margin per trade 3% → $2,430 (max DD −61%); 4.5% → $2,120 (max DD −79%).
- One trade at a time with the full balance (his rule 7): account wiped out (−99.9%) by 28 Feb 2025, after 27 trades.
- Benchmarks (same survivorship bias): BTC buy and hold 20,583 → 80,668 (+292%); equal-weight hold of the 21 coins that had perps on 28 Oct 2022: +198%.

## By year (4% sizing)
| Year (from 28 Oct) | Signals | Targets | Stops | Open | Closed P&L | Balance at end |
|---|---|---|---|---|---|---|
| 2022–23 | 107 | 16 | 91 | 0 | −$280.21 | $719.79 |
| 2023–24 | 127 | 30 | 97 | 0 | +$57.97 | $777.77 |
| 2024–25 | 165 | 23 | 142 | 0 | +$915.16 | $1,692.93 |
| 2025–26 | 189 | 22 | 161 | 6 | +$267.42 | $1,960.35 closed (+$321.54 open) |

## By coin (P&L in $, 4% sizing)
Best: HYPE +611 (3 trades, 3 targets) · HBAR +568 (32, 7) · XMR +312 (14, 6) · TAO +288 (14, 4) · BCH +271 (28, 7) · M +190 · BTC +135 (6, 2).
Worst: NEAR −561 (32 trades, 0 targets) · XLM −312 (31, 1) · LINK −208 (29, 3) · LTC −167 (26, 3) · TON −145 (9, 0) · UNI −114 (29, 5).

## Biggest winners
| Coin | Entry date | Entry | Stop | Target | Lev. | Exit | Return on margin | $ P&L |
|---|---|---|---|---|---|---|---|---|
| HYPE | 21 Jan 2026 | 21.528 | 20.27 (5.8%) | 51.496 | 8x | 20 May 2026 | +1,113% | +472 |
| ONDO | 6 Sep 2024 | 0.5718 | 0.5320 (7.0%) | 1.4859 | 5x | 2 Dec 2024 | +799% | +247 |
| ETH | 6 Sep 2024 | 2,223.7 | 2,128.5 (4.3%) | 3,980 | 10x | 6 Dec 2024 | +789% | +244 |
| AAVE | 30 Apr 2025 | 164.10 | 153.79 (6.3%) | 378.63 | 5x | 23 Aug 2025 | +653% | +241 |
| HBAR | 19 Apr 2024 | 0.08031 | 0.07542 (6.1%) | 0.14091 | 5x | 23 Apr 2024 | +377% | +200 |
| HBAR | 22 Jun 2025 | 0.13353 | 0.12463 (6.7%) | 0.28772 | 5x | 18 Jul 2025 | +577% | +193 |
| TAO | 11 Oct 2025 | 297.17 | 271.57 (8.6%) | 461.82 | 5x | 14 Oct 2025 | +277% | +172 |
| SOL | 23 Jan 2024 | 84.325 | 78.17 (7.3%) | 126.94 | 6x | 29 Feb 2024 | +303% | +157 |

## Caveats
- **Survivorship bias:** only coins in today's top 50 are tested. Coins that fell out of the top 50 during 2022–26 are missing, so real results were probably worse.
- Daily candles: stops assumed filled at the stop price; crash days (e.g. 12 Apr 2024, 10 Oct 2025, 5 Jun 2026) would have filled worse.
- Up to 22 correlated altcoin positions open at once.

*Mechanical approximation of a discretionary method. Not financial advice.*
