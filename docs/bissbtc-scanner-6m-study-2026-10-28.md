# BissBTC-style scanner: 6-month study and design (28 Oct 2026)

**Data:** Binance USDT-M perpetual klines (1w ×200, 1d ×1000, 4h ×1500), pulled 28 Oct 2026 through the built-in browser. Universe: CoinGecko top 50 on 28 Oct → 32 coins with a Binance USDT perp (stablecoins, RWA/gold tokens, WBT, LEO, CRO, OKB, RAIN excluded: no perp). "Liquid" = median daily quote volume ≥ $50M over the last 30 days (23 coins).
**Study window:** signals (reclaims) from 28 Apr to 28 Oct 2026. No fees, no slippage (except the $100 simulation below, which includes fees). When a bar touches both stop and target, the stop is counted (conservative). Coinglass liquidation data is **not** in this study (no history available).
**Code:** `study.js` / `study_v2.js` (run in the browser pane against `window.D`).

## Rules tested

**X: his 28 Oct 2026 X post** ("drop 30–50% into weekly support, break below, reclaim")
- Weekly S/R level = confirmed weekly pivot (2 bars each side) that price then moved ≥ max(20%, 2.5× median weekly range) away from within 10 weeks. Usable only after that move (no lookahead).
- Daily low breaks below the level, a daily close back above within 14 days = reclaim (entry at that close).
- Swept low is 30–65% below the highest high of the prior 120 days; the level itself is ≥ 25% below that high.
- Stop = swept low − 1%. Target = that prior high. One signal per coin per 30 days.

**C: challenge-stream style** (HTF level at a range extreme, 4h sweep + reclaim)
- Daily pivot levels (3 bars each side, move ≥ max(12%, 4× median daily range) within 20 days) plus the weekly levels above.
- Level in the bottom 25% of the prior 60-day range. 4h low sweeps ≥ 0.3 ATR below it, a 4h close back above within 24h. No weekend triggers.
- Stop = swept low − 0.3 ATR(4h). TP1 = nearest opposing level ≥ 1R away. TP2 = 60-day range high. Skip if TP2 < 2R. One per coin per 7 days.

## Results (first touch before the stop)

| Rule set | Signals | Coins | Hit 1R | Hit 2R | Hit 3R | Exp. at 2R | Exp. at 3R | Plan TP hit |
|---|---|---|---|---|---|---|---|---|
| X loose (30%+, any level) | 194 | 29 | 47.7% | 36.4% | 31.1% | +0.09R | +0.25R | 15% |
| X strict | 71 | 28 | 48.6% | 37.1% | 34.3% | +0.11R | +0.37R | 23% |
| **X strict, liquid only** | **52** | 21 | 55.8% | 46.2% | 42.3% | **+0.38R** | **+0.69R** | 27% |
| X strict, BTC/ETH/HYPE | 5 | 3 | 60% | 60% | 60% | +0.80R | +1.40R | 60% |
| C loose, longs | 462 | 31 | 46.9% | 30.0% | 20.8% | −0.10R | −0.17R | 5% |
| C loose, shorts | 422 | 32 | 46.4% | 32.8% | 25.7% | −0.02R | +0.03R | 5% |
| C strict, longs | 182 | 31 | 48.3% | 32.4% | 19.2% | −0.03R | −0.23R | 4% |
| C strict, longs, BTC/ETH/HYPE | 15 | 3 | 60% | 53.3% | 28.6% | +0.60R | +0.14R | 9% |

These expectancies are averages over **all** signals. A single account that can only hold one position at a time sees a different, path-dependent result (next section).

**Clustering:** X signals bunch on market-wide flushes (e.g. 4–5 Jun 2026: 7 signals; 28 Apr: 4). These are one market event, not independent trades.

## $100 compounding simulation: X rules with leverage (one position at a time)

**Rules of the simulation:**
- Universe: X strict, all 32 top-50 coins with a Binance perp.
- One position at a time; the first signal to trigger is taken, others ignored (his rule 7). Same-day ties: BTC/ETH/HYPE/SOL first, then market-cap rank. A new trade can start on the day the previous one closes.
- Full balance as isolated margin (his rule 6). Leverage: cap 10x for BTC/ETH/HYPE/SOL, 5x for other coins, reduced so a stop-out costs ≤ 50% of the account (his 20–50% band) and liquidation sits beyond the stop: leverage = min(cap, floor(50% ÷ stop%)), minimum 1x.
- Exit at the stop or at the previous high (X post target), whichever is first; still-open trades marked at the 28 Oct close.
- Binance taker fee 0.05% per side on notional included. Funding and slippage not included. Stops assumed filled at the stop price.

| # | Coin | Sweep / entry date | Entry zone (level → fill) | Stop (dist.) | Target (prev. high) | Lev. | Exit date | Exit price | Result | Trade P&L on account | $ P&L | Balance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | XLM | 28 Apr / 28 Apr | 0.1613 → 0.1617 | 0.1593 (1.5%) | 0.2556 | 5x | 29 Apr | 0.1593 | Stop | −7.9% | −7.92 | 92.08 |
| 2 | ADA | 29 Apr / 29 Apr | 0.2382 → 0.2444 | 0.2357 (3.6%) | 0.4373 | 5x | 23 May | 0.2357 | Stop | −18.3% | −16.85 | 75.23 |
| 3 | XMR | 28 May / 29 May | 357.7 → 396.9 | 342.3 (13.8%) | 498.9 | 3x | 1 Jun | 342.3 | Stop | −41.6% | −31.27 | 43.96 |
| 4 | BCH | 1 Jun / 1 Jun | 287.9 → 293.4 | 274.7 (6.4%) | 585.7 | 5x | 2 Jun | 274.7 | Stop | −32.4% | −14.23 | 29.73 |
| 5 | PEPE (1000) | 2 Jun / 2 Jun | 0.003101 → 0.003113 | 0.003010 (3.3%) | 0.005097 | 5x | 4 Jun | 0.003010 | Stop | −17.0% | −5.07 | 24.66 |
| 6 | ETH | 4 Jun / 4 Jun | 1,753 → 1,770 | 1,695 (4.2%) | 2,464 | 10x | 5 Jun | 1,695 | Stop | −43.4% | −10.70 | 13.97 |
| 7 | ZEC | 5 Jun / 5 Jun | 300.8 → 388.9 | 247.5 (36.4%) | 688.6 | 1x | 21 Aug | 688.6 | Target | +77.0% | +10.75 | 24.72 |
| 8 | DOGE | 21 Aug / 21 Aug | 0.08041 → 0.09157 | 0.07948 (13.2%) | 0.1186 | 3x | 15 Sep | 0.07948 | Stop | −39.9% | −9.86 | 14.85 |
| 9 | BCH | 15 Sep / 16 Sep | 218.8 → 221.0 | 209.5 (5.2%) | 404.5 | 5x | open (28 Oct) | 293.68 | Open | +163.9% | +24.35 | 39.20 |

**Result: $100 → $39.20 (−61%) after 6 months**, with trade 9 still open.

**Same signals, different fixed leverage** (same one-position rule, fees included):
| Leverage | 1x | 2x | 3x | 5x | 10x |
|---|---|---|---|---|---|
| Ending balance | $143.81 | $148.32 | $122.98 | $43.51 | $0 (liquidated on trade 3, XMR) |

Liquid coins only (≥$50M/day), same leverage rule: $100 → $51.67.

**Why it lost money:**
- 6 straight stop-outs at 8–43% of the account each took $100 down to $13.97 before the first winner.
- The big winners came while capital was locked in other trades: BTC (1 Jul, +8.1R), HYPE (3 Aug, +6.8R), AAVE, HBAR and TAO were all skipped. ZEC was held 5 Jun – 21 Aug.
- ZEC's 36% stop allowed only 1x, so the biggest move earned the least.
- The edge in the average (+0.38R to +0.69R) is real only if you can take most signals with small, equal risk; with one position and leverage-driven 20–50% risk, path dependence dominates.

**The three trades named in his X post, if taken on their own** (cherry-picked, they overlap in time and could not all be held in one one-position account): ZEC 1x +77% to the previous high; BTC 10x (60,000 → 82,830) about +380%; HYPE 7x (54.00 → 76.99) about +297%.

## Validation against his own trades
- **X post examples, all three found independently by rule X:**
  - ZEC: break 5 Jun 2026, level 300.8, swept to 250 (−63.7% from 688.6), entry 388.9 → high 1,699 in Sep (+337%; his "300%").
  - HYPE: break 31 Jul, reclaim 3 Aug, level 52.64, −33.6%, entry 54 → high 98.06 in Sep (+81%; his "80%").
  - BTC: break 30 Jun, reclaim 1 Jul, level 58,900, −30.3%, entry 60,000 → high 87,390 (+46%; his "40%"). Matches his 7 Oct course video's "$58k bottom".
- **Challenge-stream BTC calls (Oct) were NOT reproduced by rule C:** no C long fired near his 8 Oct 82,217 or 15 Oct 80k longs; the mechanical C rule fired a string of losing BTC shorts instead. His stream trades depend on discretion and the liquidation heatmap that the rules don't capture.

## Conclusions
1. The weekly X framework is mechanisable: the rules reproduce his named trades and show a positive average expectancy in liquid coins over this 6-month sample (+0.38R at a 2R exit, +0.69R at 3R).
2. Run as a single compounding account with one position at a time and 20–50% risk, the same signals lose money ($100 → $39); at 1–2x leverage they make +44% to +48%. Position sizing and trade selection, not the setup, decide the outcome.
3. The 4h challenge-style sweep, coded mechanically, has no edge (≈0 or negative). It should only arm alerts for BTC/ETH/HYPE and be confirmed manually (heatmap, BTC context).
4. Sample caveats: 6 months, one market regime (BTC 58k→87k recovery), correlated signals, daily bars can't show the intraday order of stop vs target, no funding or slippage.

## Coins 25%+ off their 120-day high on 28 Oct 2026 (watch, not signals)
QNT −48% (weekly supports 172, 163; 7-day low 173.3) · HBAR −43% (0.0719) · UNI −36% (6.89; 7-day low 6.50 already under it) · ENA −34% (0.1937, price on it) · ONDO −32% (0.385) · AAVE −30% (125.6) · SUI −29% (0.881) · ADA, XLM, LINK, AVAX, TAO, DOGE −25 to −29%. GRAM and BTW have under 30 weeks of history; CC and M fail the liquidity filter.

*Mechanical approximation of a discretionary method. Not financial advice.*
