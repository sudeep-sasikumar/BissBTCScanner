# BissBTC X-post framework: strategy research and refined rules (28 Oct 2026)

Builds on `bissbtc-x-framework-4y-backtest.md`. Goal: more winning signals, fewer losing ones.

## How the testing was done
- **Data:** Binance USDT-M perpetuals, daily and weekly candles, Jul 2021 – 28 Oct 2026, plus daily funding rates for the 32 current-top-50 coins. Signals tested 28 Oct 2022 – 28 Oct 2026.
- **Two universes:**
  - **A:** the 32 coins in today's CoinGecko top 50 (survivorship-biased).
  - **B:** a point-in-time top 50: on each day, the 50 Binance perps with the highest 30-day volume. 174 coins qualify (≥ 90 days in that top 50), including coins that later dropped out (MATIC, FTM, EOS, RNDR, AGIX, OCEAN, FTT…). A signal counts only if the coin was in the top 50 **on the signal day**.
- **Validation:**
  - **In-sample:** Oct 2022 – Oct 2024. **Out-of-sample:** Oct 2024 – Oct 2026.
  - **New coins:** coins in universe B that are not in universe A. They were never used to design the rules.
  - Each filter was kept only if it helped in all three slices: in-sample, out-of-sample and new coins.
- **Exits:** simulated day by day. The stop is checked before targets. A stop crossed at the open fills at the open. Stop moves apply from the next day.
- **Costs:** 0.05% fee per side; funding not included.
- **Engine check:** the Python engine reproduces the browser run exactly (588/588 signals). Four random trades were hand-checked against raw prices.

## What was tested
- **Exits (16 variants):**
  - fixed targets at 1R, 1.5R, 2R, 3R and 5R
  - breakeven after 1R, 1.5R, 2R or 3R; breakeven with a locked +1R
  - cut on a daily close below the reclaimed level (immediately, or after 2 days)
  - change of character: a close below the reclaim candle's low, or below the last higher low
  - partial exits (50% at 1R or 2R, then breakeven)
  - trailing stop on the 10- or 20-day low
  - time stops (10, 20 or 30 days below 1R)
- **Entries:**
  - the reclaim close (base)
  - next close above the reclaim high
  - a second close above the level
  - weekly close above the level
  - a retest limit order at the level
  - true **weekly-candle** sweep and reclaim
- **Signal parameters:** drawdown 30–50%, 30–65%, 40–65% and 30–80%; reclaim window of 3, 7 or 14 days; stop buffer of 1% or 3%; 120- or 180-day high.
- **Filters (≈35 features):**
  - **Regime:** BTC above or below its 200- and 50-day averages; 50-day vs 200-day; BTC 7/30/90-day return; BTC drawdown from its 1-year high; BTC volatility; market breadth.
  - **Coin:** distance from its own 200-day average and all-time high; whether the sweep made a new 1-year low; strength vs BTC over 30 and 90 days; 30-day volatility; liquidity; funding over 3 and 7 days.
  - **Candles:** sweep depth; days below the level; where the reclaim candle closed in its range; reclaim body and volume; distance the entry sits above the level; stop width; R:R to the previous high; level age and type.
  - **Calendar:** weekday, FOMC days and weeks, CPI days.
  - **Clustering:** how many signals fired market-wide in the same few days.

## Main findings
1. **The current rules have no edge on a survivorship-free universe.** On universe B they average +0.10R per trade with the stop/previous-high exit (+0.08R after fees) and −0.01R with the partial exit; on the new coins they lose (−0.05R). The earlier positive 4-year result relied on testing only today's surviving coins.
2. **Market regime matters most, and the direction is counter-intuitive.** Signals taken while BTC is in a bull regime (BTC above its 200-day average and its 50-day above its 200-day) do badly. The setup works when the flush is market-wide, in a bear or transition regime. That is Biss's own "buy when everyone is bearish".
   - Weekly, 30–50% drawdown, universe A: in-sample, the base exit averages +1.74R outside a bull regime vs −0.44R in one; out-of-sample, +0.92R vs +0.32R.
3. **Weekly candles beat daily.** A weekly low below the level and a weekly close back above it gives fewer false reclaims than the daily version (average 0.54R vs 0.32R on universe B, 30–50% drawdown).
4. **Use 30–50% drawdown, exactly as the X post says.** It beats 30–65%: deeper drops are often dead coins.
5. **Skip FOMC weeks.** It helped in all three slices (e.g. out-of-sample win rate 67% outside FOMC weeks vs 31% in them), but the samples are small (22–32 trades each). CPI days, weekdays and funding rates showed **no consistent effect**.
6. **Cutting on a "change of character" hurts.** Exiting on a close below the level or below the reclaim low turns many winners into losers, because these setups often wick back down before running. Breakeven alone lowers the loss rate but raises the scratch rate.
7. **The best exit for win rate is a partial plus breakeven:** take 50% at 1R, move the stop to entry, and leave the rest for the previous high.
8. **What did not survive validation:** retest limit entries (a fill-and-stop on the same bar had been wrongly skipped; corrected), funding, relative strength, volatility, reclaim-candle shape and level age. All were noise out-of-sample or on new coins.

## Refined rules
1. **Universe:** top-50 coins with a liquid perp (point-in-time).
2. **Level:** a weekly support or resistance level that price moved ≥ 20% away from within 10 weeks (time + distance).
3. **Setup:** the coin is 30–50% below its 120-day high when the sweep happens.
4. **Trigger:** a **weekly** low below the level, then a **weekly close back above it** within 3 weeks. Entry at the weekly close.
5. **Regime filter:** no signals while BTC is in a bull regime (close above the 200-day average and 50-day above 200-day).
6. **Calendar filter:** no signals in a week within 7 days of an FOMC decision.
7. **Stop:** 1% below the swept low. **Management:** close 50% at +1R, move the stop to entry, and target the previous (120-day) high with the rest.
8. **Optional quality filter:** stop ≤ 12% gives a higher average R (1.22 vs 0.97) but fewer trades (99 vs 158) and the same win rate.

## Results, universe B (point-in-time top 50), 28 Oct 2022 – 28 Oct 2026
| Rules | Trades | Win | Loss | Avg R (after fees) |
|---|---|---|---|---|
| Current X rules (daily, no filters), partial exit | 903 | 45% | 55% | −0.01 |
| **Refined, partial 50% @1R + breakeven** | **158** | **68%** | **29%** | **+0.97** |
| Refined: in-sample / out-of-sample / new coins | 89 / 69 / 56 | 69% / 67% / 61% | 31% / 26% / 34% | +0.89 / +1.07 / +0.62 |
| Refined, exit at 1R only | 158 | 68% | 32% | +0.36 |
| Refined, stop / previous high | 158 | 37% | 59% | +1.79 |
| Refined, TP 2R | 158 | 51% | 49% | +0.53 |

- **By year (refined, partial exit):**

  | Year | Trades | Win |
  |---|---|---|
  | 2022 | 12 | 58% |
  | 2023 | 43 | 70% |
  | 2024 | 34 | 71% |
  | 2025 | 19 | 79% |
  | 2026 | 50 | 62% |

- **Streaks and exits:** longest losing streak 7; median hold 15.5 days; 62 breakeven exits, 50 targets, 46 stops.
- **Concentration:** the top 5 trades made 71 of the 153 R. Without the top 10 trades, the average is still +0.38R.

**$1,000, every signal taken, risk per trade as % of equity** (leverage capped at 10x for BTC/ETH/HYPE/SOL and 5x for others):
| Risk / trade | End balance | Max drawdown | Trades skipped (no free margin) |
|---|---|---|---|
| 2% | $11,235 | −16% | 0 |
| 5% | $44,641 | −32% | 21 |
| 10% | $54,374 | −47% | 59 |
| Current rules, 2% | $158 | −93% | – |

**Ablation** (refined, 5% risk; one filter removed at a time):
| Variant | Trades | Win | Loss | Avg R | $1,000 → | Max DD |
|---|---|---|---|---|---|---|
| Refined + stop ≤ 12% | 99 | 69% | 31% | 1.22 | $21,160 | −29% |
| Without the BTC regime filter | 182 | 56% | 44% | 0.55 | $5,768 | −69% |
| Without skipping FOMC weeks | 131 | 64% | 36% | 1.08 | $17,952 | −39% |
| Daily sweep instead of weekly | 199 | 52% | 48% | 0.55 | $9,009 | −82% |
| Drawdown 30–65% | 119 | 66% | 34% | 0.81 | $9,586 | −37% |

(The first four rows include the stop ≤ 12% filter; the refined rules without it are the 158-trade line above.)

## Status on 28 Oct 2026
BTC has been in a bull regime since 8 Sep 2026 (close 80,563; 50-day 81,889; 200-day 73,073), so the refined rules give **no new signals now**. The last refined signal was 30 Aug 2026. The regime flips around the threshold at times (e.g. Mar 2025), so the scanner should require 2–3 consecutive days before switching.

## Caveats
- The rules were chosen after looking at 2022–2026 data. The consistency checks (time halves, unseen coins) reduce overfitting but do not remove it. The real test is forward paper trading.
- Results lean on a few large winners and on 2026. The edge is real but modest without them.
- Up to 18 positions can be open at once in correlated coins, so a market-wide crash hits many at the same time.
- Daily candles cannot show the order of events inside a day. Funding, slippage and coins without Binance data are not included.
- Geopolitical news can't be backtested systematically. The BTC regime and volatility filters are the proxies used here.
- "No losing signals" is not achievable. About 29–31% of refined signals still lose a full 1R.

*Not financial advice.*

## Update 29 Oct 2026: universe size (top 50 → 500) and risk 2–5%
**Universe:** Binance's full historical USDT-perp list (data.binance.vision, about 900 contracts, delisted ones included). After removing stock, commodity, FX and index contracts and stablecoins, 673 crypto coins have data. Each day they are ranked by 30-day average traded volume; a signal counts for "top N" only if the coin was ranked ≤ N on the signal day.
**Coins available to rank:** about 140 in Nov 2022, about 300 in Nov 2024, about 650 now. Before 2025, "top 200/400/500" means every Binance perp.
**Rules:** the refined rules above (weekly sweep and reclaim, 30–50% drawdown, BTC not in a bull regime, no FOMC weeks; 50% off at +1R, stop to entry, rest to the previous high). Fees included.
**Dollar figures:** signals often fire in the same week, and which ones get margin first changes the result. Each case was therefore run 300 times with a random order within the week; the table shows the median and the 10th-percentile outcome. Leverage caps: 10x for BTC/ETH/HYPE/SOL, 5x for others. A signal is skipped if there isn't enough free margin.

| Universe | Trades | Win | Loss | Avg R | Avg R, first 2 yrs | Avg R, last 2 yrs |
|---|---|---|---|---|---|---|
| Top 50 | 163 | 66% | 31% | +0.92 | +0.89 | +0.95 |
| Top 100 | 269 | 60% | 37% | +0.62 | +0.68 | +0.55 |
| Top 200 | 434 | 58% | 40% | +0.48 | +0.57 | +0.33 |
| Top 400 | 630 | 53% | 45% | +0.28 | +0.38 | +0.18 |
| Top 500 | 686 | 53% | 46% | +0.28 | +0.38 | +0.19 |

By rank band (avg R): 1–50 +0.92 · 51–100 +0.17 (last 2 yrs −0.24) · 101–200 +0.24 (last 2 yrs −0.08) · 201–400 −0.16 · 401–500 +0.21 (56 trades, all in the last 2 years).

**$1,000 start, Oct 2022 – Oct 2026: median end balance / worst-10% end balance / median max drawdown**
| Universe | 2% risk | 3% risk | 4% risk | 5% risk |
|---|---|---|---|---|
| Top 50 | $10,585 / $10,585 / 17% | $24,749 / $14,655 / 26% | $25,152 / $23,229 / 31% | $43,598 / $25,390 / 42% |
| Top 100 | $10,773 / $10,648 / 35% | $13,606 / $11,770 / 44% | $17,563 / $14,820 / 47% | $28,049 / $20,433 / 53% |
| Top 200 | $9,111 / $8,167 / 44% | $11,889 / $9,752 / 51% | $18,405 / $12,607 / 55% | $19,820 / $11,260 / 54% |
| Top 400 | $5,452 / $4,496 / 61% | $8,668 / $6,131 / 53% | $8,790 / $5,471 / 57% | $11,249 / $6,512 / 54% |
| Top 500 | $5,938 / $4,822 / 59% | $9,719 / $6,958 / 48% | $9,976 / $6,643 / 51% | $11,844 / $6,230 / 56% |

Signals skipped for lack of margin, median at 5% risk: 21 (top 50), 89 (top 100), 221 (top 200), 384 (top 400), 436 (top 500).

**Conclusions:**
- Keep the scanner to the **top 50**. Ranks 51–500 together add roughly zero edge after fees (about +0.07R) and turn negative in the last 2 years. They mainly add drawdown.
- These results don't include extra slippage on thin coins, Blofin listing gaps or liquidity limits, all of which make the larger universes worse.
- **Top 50 risk choice:** 4% risk gives a median max drawdown of about 31%. 5% gives about 42%, with a worst-10% end balance of $25,390.
- **Correction to the earlier top-50 5% figure:** −32% drawdown, $44,641 came from a slightly smaller coin set (158 trades). The 5 extra trades here are coins briefly in the top 50; 4 of them lost.
