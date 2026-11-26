# Research data the scanner collects

From 26 Nov 2026 the paper scanner also records research data in `data/biss.sqlite`, stored in the `biss_data` volume
on the VPS. The goal is to review, after a few weeks or months, what worked and what did not, and to propose
improvements. **Collection only records.** It never changes alerts, filters, sizing or paper trades. Any change to the
scanner is made only after the owner approves it.

Download a consistent copy from the dashboard's **Data** tab ("Download the database"), then run
`python scripts/u13_live_review.py <file.sqlite>`.

## What is stored and why

| Table | When | What | Questions it answers |
|---|---|---|---|
| `setups` | every scan | **every** setup the scanner computes, passing or not, plus ones skipped (weekend sweep, attempts), with every feature as JSON: level type, timeframe, touches, age, sweep depth (% and ATR), reclaim and entry times, stop %, TP1, TP2, R:R, drawdown, location, FOMC and quarter-close distance, BTC regime, tier, conviction, size, leverage, liquidation price, scanner version and config hash | Which filters keep out winners or let in losers? Does the live scanner find what the backtest would? |
| `setup_tracks` | every scan, for 30 days per setup | forward path in R: MFE and MAE overall and at 1, 3, 7, 14 and 30 days; first touch of −1R, +0.5R, +1R, +2R, +3R, TP1 and TP2; first close back through the level; same-bar ambiguity; result under five exits (the live plan, fixed 2R, fixed 3R, all at TP1, all at TP2) | Best exit and target choice, time stops, how deep trades go before working, the cost of the early-exit rule |
| `bars_15m`, `bars_1d` | every scan, hourly | the exact WEEX bars the scanner saw, plus its daily bars | Replay any rule change on live data, and check live against backtest data (WEEX vs Binance) |
| `market_snap` | every scan (15 min) | WEEX last, mark and index price, funding (last and forecast), 24h volume and change, for the scanned symbols plus BTC and ETH | Funding and basis at entry, and whether crowded funding predicts failure |
| `deriv_snap` | hourly | Binance open interest (coins and USD), funding, mark; global and top-trader long/short ratios; taker buy/sell ratio; WEEX open interest | Positioning around sweeps: does a sweep with falling OI (stops flushed) work better? |
| `book_snap` | hourly for every symbol, and when a setup or alert appears | WEEX spread and depth (USD) within 0.5%, 1% and 2% of mid | Realistic slippage for the alerted size; whether thin books hurt results |
| `liquidations` | continuous (websocket) | Binance liquidation orders for the scanned symbols plus BTC and ETH: side, price, size | Did a liquidation cascade at the level (the manual checklist's Coinglass question) separate winners from losers? |
| `universe_snap` | daily | top 150 WEEX crypto perps by 24h volume, rank, and whether scanned | How far the top-50 list drifts. It is fixed at container start, so this shows what a daily refresh would change. |
| `scans` | every scan | scan time, symbols, failures, setups found, BTC close, SMA50, SMA200, bull and bear regime | Health, and the regime context of every period |
| `events` | as they happen | alerts, paper trade opens and closes, starts, collector errors | Live record matched against the tracks |

The outcome tracker uses the same rule as the backtest when one bar touches both levels: the stop counts first. R in the tracks is
**gross of fees**; the review script subtracts estimated costs (taker in, taker on stops, maker on targets,
slippage by tier). The tracks are kept on WEEX bars, the exchange you trade, while the backtest used Binance bars.

## How much space it takes
Roughly 50 symbols × 96 bars a day (15m bars) + 1,200 hourly rows + snapshots, about 10–20 MB a month. Liquidations
depend on the market (filtered to the scanned symbols). Nothing is deleted automatically.

## What a review will look at (after about 4–8 weeks; more is better for weekly setups)
1. Live vs backtest: R per trade, win %, how often setups occur, slippage at alert time.
2. The counterfactual for each filter: setups that failed only that filter, and their outcomes.
3. Exits: the live plan vs fixed 2R or 3R vs TP1 or TP2, and the MFE and MAE distributions. Where would a time stop or a tighter TP1 have helped?
4. Context: funding, OI change, long/short ratio, liquidations at the level, book depth, BTC regime. Which of them separate
   winners from losers? Each candidate rule has to show the effect both before and after the review date, then it goes to the
   owner for approval.
5. Universe: whether a daily refresh of the top-50 list would have added setups that worked.

Weekly setups are rare, about 8 a month that pass and many more that fail. Conclusions about individual filters need months, not weeks.
The setups that fail the filters, which are also tracked, give more data sooner.
