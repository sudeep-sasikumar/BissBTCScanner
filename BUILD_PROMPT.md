# Prompt: build a BissBTC-style "HTF sweep → LTF reclaim" leverage system on WEEX futures

*How to use: put this file and the `docs/` folder beside it in the root of a new repo, open Claude Code there, and say: "Read BUILD_PROMPT.md and follow it." Values in `{{ }}` are defaults you can change.*

---

## 0. Role, goal and files

You are a quantitative trading-system engineer. Build, backtest and (only after validation) run as a **paper-trading** signal scanner a system that copies one specific BissBTC setup:

> A **higher-timeframe (HTF) support or resistance level** (monthly or weekly) is **swept**: price trades through it, taking the stops and liquidations sitting there. Price then **reclaims** the level, closing back on the original side. The trade is **executed on a lower timeframe (LTF)**, default 15m, once the reclaim is confirmed, with the stop beyond the swept extreme. Instruments are **WEEX USDT-margined perpetual futures**, crypto and TradeFi (stocks etc.), traded with leverage.

**Reference files (read all of them before writing code). Paths are relative to this file:**

| File | What it gives you |
|---|---|
| `docs/bissbtc-style-playbook.md` | His method. Most relevant: sections 3–8, 15 and 16. |
| `docs/bissbtc-scanner-6m-study-2026-10-28.md` | Mechanical versions already tested, incl. why the 4h "challenge-style" rule had no edge. |
| `docs/bissbtc-x-framework-strategy-research.md` | Refined weekly rules; filters that did and didn't survive validation; exit studies; sizing and universe-size results. |
| `docs/bissbtc-x-framework-4y-backtest.md` | The earlier 4-year backtest (older rules) and its trade-list column format. |
| `docs/bissbtc-2026-11-02-stream-setups.md`, `docs/bissbtc-2026-11-17-stream-setups.md`, `docs/bissbtc-2026-11-23-stream-setups.md` | Recent live examples of this exact setup (BTC, ZEC, HYPE) with his levels. |

These are exported copies (25 Nov 2026) of docs kept in Sudeep's claude.ai Project "BissBTC Trading Challenge". Where this prompt and the docs disagree, follow the docs and tell me. Note: the earlier studies used **Binance** data and a **Blofin**-style account; this build uses **WEEX**.

## 1. What BissBTC actually does (spec, with sources)

1. **Levels.** Plain horizontal S/R only, no indicators. A level is valid only if price was pushed away from it in both **time and distance**. Resistance that breaks becomes support, and the reverse. A fake-out through a level doesn't cancel it if price gets back inside. Key lines also include the yearly, monthly and weekly opens and prior range extremes. (playbook §3, §15)
2. **Top-down.** Monthly and weekly set the level and direction, daily and 4h set structure, and 15m–1m is only for the entry. He calls top-down "the most important step". (playbook §15)
3. **Location.** He only trades extremes: range lows for longs, range highs for shorts. Never mid-range. (playbook §1)
4. **The trap.** Obvious lows hold stops and long liquidations. The sweep takes them out, and breakdown shorts open below support. The reclaim forces those shorts to buy back, which fuels the move. "Wait for people to get trapped." (playbook §1, §15)
5. **Trigger.** "Not blindly aping down here." He wants price below the lows, sometimes "a few candle closes below", then **back above** the level. **No limit orders into the level** for this setup. "If it keeps falling through with no bounce, I don't take it." He doesn't wait for a daily close to confirm; he watches the LTF live. (Nov 2, 17, 23 streams; playbook §5)
6. **Stop.** Below the swept low, and **a little further, not directly under it**, "because you can still run multiple times". The stop goes where the idea is wrong, not wherever is tightest. (playbook §6)
7. **Targets.** TP1 at the nearest opposing level or liquidity. TP2 at the other side of the range or the prior high. Typical box R:R is about 2.5–3.5. He takes profit in pieces when unsure. (streams; playbook §8)
8. **Conviction tiers.** A sweep of a bigger level (weekly/monthly, into a big liquidation cluster) gets more risk. A minor LTF sweep gets less. Shorts get less than longs, and alts less than BTC. (playbook §4, §7)
9. **Timing.** No trades on weekend sweeps: he skipped the Nov 2026 BTC low because it printed on a Saturday. He waited out a pre-FOMC entry ("wrong side of FOMC"). He expects chop near quarterly candle closes. (playbook §3; Nov 23 stream)
10. **Universe (his).** For his challenge: BTC first, then ETH and HYPE, with ZEC as a smaller secondary. No low caps. (playbook §2; Nov streams) **This build deliberately uses a wider universe (section 4); that is a hypothesis to test, not his method.**
11. **Leverage (his).** "Leverage doesn't matter, position size does." Size = risk ÷ stop distance; leverage is whatever that size needs. Highest leverage only on liquid majors with tight stops; little or none on volatile small caps. (playbook §7)

## 2. What the project's backtests already found (don't relearn these)

- **The mechanical 4h sweep-and-reclaim ("rule C") had no edge** in a 6-month study (about −0.1R to +0.03R across hundreds of signals). It only looked positive on BTC/ETH/HYPE, and on small samples. It also failed to reproduce his October BTC longs. **Lower-timeframe reclaims on their own produce many false reclaims.**
- **Weekly confirmation beat daily.** A weekly low below the level, then a weekly close back above it, averaged 0.54R vs 0.32R for the daily version (top-50, point-in-time universe).
- Refined weekly rules: 30–50% below the 120-day high; BTC **not** in a bull regime; skip FOMC weeks; 50% off at +1R, stop to entry, rest to the prior high. Result: **158 trades, 68% win, +0.97R average after fees** (Oct 2022 – Oct 2026). It held in-sample, out-of-sample and on unseen coins.
- **Cutting on a "change of character" hurt.** Exiting on a close back below the level or below the reclaim candle's low turned winners into losers, because these setups often wick back down before running.
- Funding, relative strength, volatility, reclaim-candle shape, level age and retest-limit entries were all **noise out-of-sample**.
- **Universe size:** top 50 by volume = +0.92R; ranks 51–500 together ≈ +0.07R and negative in the last 2 years. They mainly added drawdown. Thin-coin slippage wasn't even modelled.
- **Sizing decides the outcome.** One position at a time at 20–50% risk turned +EV signals into $100 → $39 (and 10x fixed leverage was liquidated on trade 3). Equal small risk (2–5%) compounded well.
- **All of the above is crypto only.** Stock and other TradeFi contracts were excluded from every study; their behaviour is **untested**.

**Implication:** a 15m trigger and a wider WEEX universe each have to earn their place against the weekly-close, top-50-crypto baseline. Test them; don't assume they help.

## 3. Venue and data: WEEX futures

**3.1 Universe discovery (do first, report before backtesting)**
- Pull the full WEEX USDT-M perpetual contract list and classify each contract: crypto, stock, index, commodity, FX, other.
- For each contract record: symbol, asset class, listing date, max leverage and leverage/notional brackets, tick size, minimum size, taker/maker fee, funding interval, 30-day volume, and trading hours or market-closure behaviour (TradeFi).
- **Endpoints (from WEEX's docs index; verify each one before relying on it, the parameter details weren't confirmed):**
  - base URL `https://api-contract.weex.com` (seen in WEEX's own examples)
  - `GET /capi/v3/market/exchangeInfo`: contract info
  - `GET /capi/v3/market/riskLimits`: notional and leverage brackets
  - `GET /capi/v3/market/klines` and `GET /capi/v3/market/historyKlines`: candles (check intervals, max `limit`, `startTime`/`endTime` paging)
  - `GET /capi/v3/market/markPriceKlines`, `GET /capi/v3/market/indexPriceKlines`
  - docs index: `https://www.weex.com/api-doc/llms.txt`
  - `ccxt` lists WEEX with contract support (`fetchMarkets`, `fetchOHLCV` max 300 bars per call, `fetchFundingRateHistory`, `fetchOpenInterest`). Use it if it's simpler, but verify its output against the raw API.
- **Use WEEX's real fees and leverage brackets.** If you can't get them, default to 0.05% per side and caps of 10x (BTC/ETH), 5x (other crypto), `{{3x}}` (TradeFi), and tell me.

**3.2 History for backtesting**
- First measure how far back WEEX candles go for each timeframe (1M, 1w, 1d, 4h, 15m, 1m).
- If WEEX history is too short:
  - **Crypto:** use Binance USDT-M history (data.binance.vision, delisted contracts included) for the same coins, mapped by base asset, and flag any coin with no Binance history.
  - **TradeFi:** Binance also lists some stock/commodity/index perps; use them where they exist. Otherwise use the **underlying** market's history from a provider I choose (ask me before paying for or signing up to any data source). Record which source each backtest used.
- **Price basis:** build levels on last-price candles; check stops against **mark price** where available (that's what triggers liquidation). Report both if they differ materially.

**3.3 TradeFi specifics (stocks etc.)**
- Find out exactly how WEEX prices these perps when the underlying market is closed (weekends, overnight, holidays): does it trade 24/7 on an oracle, freeze, or widen? Document it before designing anything.
- Gaps: a weekend or overnight gap can jump straight through a stop. Model fills at the first available price beyond the stop, not at the stop.
- Add an **earnings / company-event filter** (no new trade within `{{2}}` sessions of earnings) and keep the FOMC filter.
- Levels: test levels built from (a) the perp's own candles and (b) the underlying's regular-session candles, and report which works.
- Report TradeFi results **separately** from crypto. Never blend them into one headline number.

## 4. Universe tiers (each tested separately)

- **T1 majors:** BTC, ETH, plus HYPE, SOL, ZEC if listed (his own universe).
- **T2 crypto top 50:** point-in-time, by 30-day volume on WEEX (or Binance if WEEX history is short).
- **T3 crypto 51+:** everything else that passes a liquidity floor of `{{$20M}}` 30-day median daily volume.
- **T4 TradeFi:** all stock/index/commodity contracts that pass the same floor.
- Results per tier. **A tier goes live only if it passes section 8 on its own.** Based on section 2, I expect T3 to fail; prove it either way.

## 5. Definitions (implement exactly, all parameters configurable)

**5.1 HTF levels** (monthly and weekly, built separately and tagged by source TF)

- **Swing pivots.** A pivot is confirmed only after `{{pivot_bars: 2}}` bars on each side.
- **Validation.** After the pivot, price must move ≥ `max({{min_move_pct: 20%}}, {{k: 2.5}} × median bar range)` away within `{{N: 10}}` bars. The level is usable **only from the bar after that move completes**, so there's no lookahead.
- **Also include as levels:** yearly, monthly and weekly opens; prior HTF range high and low.
- **Merge** levels within `{{merge_pct: 0.5%}}` into a zone. Keep a touch count and the last reaction date.
- **Location filter:** a long level must sit in the bottom `{{25%}}` of the prior `{{60-day}}` range, or be the range low. Mirror this for shorts.

**5.2 Sweep** (the HTF event)

- **Long:** a 15m low trades below the level by ≥ `{{sweep_min: 0.3 × ATR(4h)}}`. Record the swept low (the lowest low until the reclaim).
- **Max depth:** if price goes more than `{{sweep_max: 1.5 × ATR(daily)}}` below, or a **daily close** stays below for more than `{{max_days_below: 3}}` days, mark it as **acceptance below, not a sweep**. Cancel the setup. The level is now resistance.
- **Weekend / market-closed:** ignore sweeps whose low prints Saturday or Sunday (UTC), or while a TradeFi contract's underlying market is closed, as triggers. Keep them for levels.

**5.3 Reclaim** (implement all three as variants; the backtest picks)

- **R1 (15m):** `{{n_closes: 2}}` consecutive 15m closes back above the level, within `{{reclaim_window: 72h}}` of the swept low.
- **R2 (4h):** a 4h close back above the level.
- **R3 (baseline):** a daily close (weekly levels) or weekly close back above, as in the refined X rules.

**5.4 Entry** (on 15m, after the reclaim)

- **E1:** market entry at the reclaim close.
- **E2:** the first 15m pullback that holds the level, a higher low above the level. Enter on the close back up. Expire after `{{24h}}`.
- **No resting limit inside the level before the reclaim.** This is his explicit rule.
- **Max attempts:** `{{2}}` per sweep. A second sweep below the first swept low that reclaims again is a valid re-entry with a new stop. This is his "can run multiple times".

**5.5 Stop**

- Swept low minus `{{stop_buffer: max(0.3 × ATR(4h), 1%)}}`. Never place it directly at the low.
- Skip the trade if the stop distance is over `{{max_stop: 12%}}`. That filter raised average R in the weekly study.
- **Default: no early "close below level" exit.** Test it only as a variant; section 2 shows it hurt.

**5.6 Targets and management**

- **TP1:** nearest opposing HTF level or zone ≥ 1R away.
- **TP2:** opposite range extreme, or the prior 120-day high for deep-drawdown names.
- **Skip the trade if TP2 is under `{{min_rr: 2R}}`.**
- **Default management** (best win rate in project research): close 50% at +1R, move the stop to entry, run the rest to TP2.
- **Variants:**
  - fixed 2R or 3R;
  - partial at TP1;
  - trailing below 4h higher lows (his "trail only with a reason");
  - time stop after `{{20}}` days below 1R.

**5.7 Shorts (mirror, lower priority)**

- A sweep above HTF resistance (the yearly open, a range high), then 15m closes back below.
- He takes these only when "blaringly obvious", and with **half the long risk**.
- Report shorts separately.

## 6. Context filters (each one must be tested, not assumed)

- **F1, BTC regime** (crypto):
  - Bull = BTC close above its 200-day average **and** the 50-day above the 200-day.
  - The project found alt sweep-longs work mainly **outside** bull regimes.
  - Test separately for BTC itself, for alts, and for TradeFi (where an index regime such as the S&P 500 vs its 200-day may fit better).
  - Require `{{2–3}}` consecutive days to flip the regime.
- **F2, drawdown:** the swept low sits 30–50% below the 120-day high (crypto alts). For TradeFi, test `{{10–30%}}` bands, since stocks move less.
- **F3, calendar:** skip within 7 days of an FOMC decision. Skip a sweep within `{{3}}` days of a quarterly candle close. Earnings filter for stocks (3.3).
- **F4, location:** range-extreme only (5.1). Never mid-range.
- **F5, liquidity:** 30-day median daily volume ≥ the tier floor. Spread and depth check at entry on live data.
- **F6, optional data** (only if history exists; report coverage): open-interest drop and liquidation volume during the sweep, as a proxy for "trapped traders". Coinglass heatmap history isn't available; keep the heatmap as a **manual confirmation step**, not a coded rule.

## 7. Sizing, leverage and liquidation

- **Risk:** `{{risk_pct: 2–5%}}` of equity per trade (my tolerance is about 30% max drawdown at 5% risk).
- **Position size** = risk$ ÷ stop%. **Leverage** = position size ÷ margin allocated. Leverage is an output, not a setting.
- **Hard caps:** the lower of WEEX's per-contract max leverage (from `riskLimits`) and my caps (10x BTC/ETH, 5x other crypto, `{{3x}}` TradeFi).
- **Liquidation rule:** the liquidation price must sit beyond the stop by at least `{{liq_buffer: 1 × stop distance}}`, computed with WEEX's maintenance-margin brackets. If it can't, cut size, don't widen the stop.
- **Report the leverage each trade actually needed.** Report how often the 15m version (tighter stops) pushed leverage to the cap, and how many trades were skipped or shrunk because of it. "Leverage plays" have to show up as better R per unit of risk after fees and funding, not as bigger position sizes.
- **Tiering:**
  - Monthly level, or weekly level + F1 + F2 all satisfied: 1.0× risk.
  - Weekly level only: 0.6×.
  - Shorts: 0.5×.
  - TradeFi: `{{0.5×}}` until it has proven itself.
- **Modes:** (a) all signals with equal small risk, a cap on total open risk of `{{20%}}`, and a cap of `{{3}}` concurrent positions per correlated cluster (e.g. "crypto alts", "US tech stocks"); (b) his challenge rule, one position at a time, first fill wins, 20–50% risk. **Mode (b) is a stress test only.** Report it, but don't recommend it unless it beats (a) on median and worst-10% outcomes.
- **Costs:** WEEX fees, **funding** (WEEX history if available; otherwise Binance funding for crypto and a stated assumption for TradeFi), and slippage of `{{0.02%}}` on T1, `{{0.1%}}` on T2/T4 and `{{0.3%}}` on T3.

## 8. Validation protocol (required before any live alerts)

1. Period Oct 2022 – present (or the longest the data allows per tier). In-sample is the first half, out-of-sample the second, plus a holdout of symbols not used for design.
2. Keep a rule or filter only if it helps in **all three slices**.
3. **Ablation table:** remove one filter at a time.
4. **Compare every variant to two baselines:**
   - the refined weekly-close rules (R3/E1, +0.97R, 68% win on crypto top 50);
   - the plain 4h rule C (≈0R).

   **The 15m version is adopted only if it beats R3 on average R after fees and funding, or matches it with a materially tighter stop and lower drawdown.**
5. Use **1m data inside 15m bars** to resolve stop vs target order. If 1m isn't available, assume the stop is hit first.
6. **Path-dependence:** run 300 random within-week orderings of signals. Report the median and worst-10% end balance and the max drawdown at 2%, 3%, 4% and 5% risk, per tier.
7. **Reference cases the system must detect, with roughly his levels:**
   - BTC weekly level ~58.9k, swept 30 Jun 2026, reclaimed 1 Jul 2026.
   - HYPE ~52.64 level, swept 31 Jul 2026, reclaimed 3 Aug 2026.
   - ZEC ~300.8, swept 5 Jun 2026.
   - BTC "below the lows, back above ~61.5k" (17–20 Nov 2026).
   - BTC 57.3–57.7k higher-low plan (23 Nov 2026).

   Report detections, misses and why.
8. Report **signal frequency per level type and per tier**. Monthly-level sweeps may be rare; if there are too few to judge, say so and don't over-fit to them.

## 9. Output

**A. Universe report** (section 3.1): every WEEX contract, its class, history depth, leverage brackets, fees and liquidity tier.

**B. Backtest report:**
- a table per variant and per tier: trades, win/loss/scratch %, average R, median R, profit factor, max losing streak, max drawdown, median hold, exposure, average and max leverage used, liquidation-buffer violations, funding paid;
- results by level type (monthly, weekly, open) and by year;
- the top-10 trade concentration;
- a plain-English verdict.

**C. Scanner** (only for tiers that pass section 8). It runs 24/7 on my VPS (Hostinger, Kuala Lumpur), in a new repo, and sends **paper-trade** alerts to a new Telegram bot (I'll supply the token; never hard-code it). Each alert includes:
- symbol, asset class, direction, HTF level (price, TF, type, touches), swept low and sweep depth;
- reclaim time and TF;
- entry range, stop (with distance %), TP1, TP2, R:R, risk tier;
- position size and implied leverage at my risk %, WEEX max leverage, and the liquidation price vs the stop;
- invalidation condition;
- filters passed or failed;
- a reminder to do the **manual checklist**: Coinglass liquidation cluster at the level, BTC context, no weekend or market-closed sweep, no FOMC week, no earnings (stocks).

**D. Trade journal:** a CSV of every signal and outcome, with the columns coin, entry_date, entry, stop, stop_pct, target, leverage, margin_usd, result, exit_date, exit_price, trade_return_pct, pnl_usd, closed_balance_after (the same as the earlier 4-year backtest), plus asset_class, tier, level_tf, reclaim_variant, funding_usd and fees_usd.

## 10. Ground rules

- No lookahead: levels, regimes, universes and tiers are known only as of the signal bar.
- Don't tune on the full sample and report it as out-of-sample.
- State every assumption, especially anything about WEEX endpoints, fees, leverage brackets or TradeFi trading hours you couldn't verify.
- If a result looks too good, check fills, gaps and bar ordering before reporting it.
- **Paper only.** No API keys with trading permission, and no live orders, until I explicitly approve.
- If a result contradicts BissBTC's claims, report the data rather than his claim.
- Stop and ask me before: paying for any data, choosing a stock-data provider, or dropping a tier I asked for.
