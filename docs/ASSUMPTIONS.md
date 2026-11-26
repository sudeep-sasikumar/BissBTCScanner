# Assumptions and things I couldn't verify

## WEEX API (checked against the live API, 25-26 Nov 2026)
- Base `https://api-contract.weex.com`, prefix `/capi/v3/market/`. Public endpoints, no key.
- `klines` returns the newest bar first, at most 1,000 bars, with no paging. `historyKlines` needs **both** `startTime` and `endTime`, a range of 90 days or less, `limit` up to 100, and `priceType` LAST/INDEX/MARK. It rejects an `endTime` even slightly in the future, so code keeps 2 minutes of margin. There is no `1M` interval; monthly bars are built from daily.
- Rate limit reported by `exchangeInfo`: REQUEST_WEIGHT 500 per 10 s.
- Fees: every contract returns taker 0.08% and maker 0.02%; `apiTakerFeeRate` is not returned. The backtest uses these, not the prompt's 0.05% default. VIP or referral discounts are not modelled.
- Leverage brackets: `riskLimits` gives notional caps, max initial leverage and maintenance margin ratios per contract. These are **today's** brackets, applied to the whole history. For Binance-history coins not listed on WEEX, the default is MMR 1% and max 20x.
- Funding: WEEX `fundingRate` history only returns about the last 6 months, so the backtest uses Binance funding for crypto. TradeFi assumes 0.01% per 8 h against longs (a stated assumption).
- Funding interval comes from `delivery` (settlement times per day): 8 h for most contracts, 4 h or 1 h for some.

## History
- Crypto candles are Binance USDT-M (data.binance.vision monthly files plus fapi REST for the tail). Levels and point-in-time tiers rank all Binance crypto perps, delisted ones included, by 30-day average quote volume, shifted one day.
- WEEX prices are assumed equal to Binance's for the same base asset. The live scanner uses WEEX 15m bars for triggers and Binance daily bars for levels, the same as the backtest.
- 1m bars inside an ambiguous 15m bar come from Binance daily 1m files. If none exist, the stop is assumed first.
- Mark price: Binance `markPriceKlines` 15m is fetched for a sample of trades (report section 12). The main backtest triggers stops on last price.

## TradeFi
- WEEX TradeFi perps trade 24/7 (`reports/tradfi_hours.csv`). WEEX and Binance perp history only starts in 2026.
- Underlying history and earnings dates come from Yahoo Finance via `yfinance`: free, no account, unofficial, and it can be wrong (split-adjusted with `auto_adjust`). Contracts with no listed underlying (OpenAI, SpaceX, Unitree and other pre-IPO names) have no history.
- Yahoo's earnings dates only cover recent years (about 40 quarters requested). Older signals with no known earnings date pass the earnings filter.
- The S&P 500 regime uses SPY with the same definition as the BTC regime.

## Calendar
- FOMC decision dates for 2022–2026 are entered by hand. 2027 is the Fed's tentative schedule; **check it before live use**.
- "Within 7 days of FOMC" is taken symmetrically (±7 days from the entry). Quarter-close: the sweep is within 3 days of 1 Jan/Apr/Jul/Oct 00:00 UTC.
- Weekend = Saturday or Sunday UTC.

## Interpretations of the spec
- R3 is split into R3d (daily close back above) and R3w (weekly close back above), both within 3 weeks. The refined-rules baseline is a separate, daily-bar reproduction (`biss/baselines.py`).
- Acceptance rules (deeper than 1.5×ATR(daily), or more than 3 daily closes below) apply to every reclaim variant, R3 included, as section 5.2 says.
- One position per symbol and side at a time. When several levels on one coin trigger together, the first entry wins.
- TP2 is the 120-day high when the swept low is 30% or more below it, otherwise the 60-day range high. TP1 is the nearest level at least 1R away, falling back to +1R.
- Open risk counts each position's full initial risk until it exits, even after the stop moves to entry (conservative).
- Correlated clusters: crypto_majors (BTC, ETH), crypto_alts, us_tech, stocks_other, index, commodity, fx.
- Holdout symbols: a deterministic 30% hash of the base asset (BTC and ETH never held out). IS is before 15 Oct 2024, OOS after.

## Not done
- F6 (open-interest drop and liquidation volume during the sweep) is not implemented. Binance OI history exists (`metrics` files from about Dec 2021); liquidation history doesn't. The Coinglass heatmap stays a manual checklist item.
- No live spread or depth check at entry. The scanner shows the WEEX mark price, but you should check the order book yourself.
