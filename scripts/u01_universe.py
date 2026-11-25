"""Section 3.1: WEEX universe discovery.

Writes data/weex/{exchange_info,risk_limits,ticker24h}.json, data/weex/daily/<SYM>.parquet (last 1000 days),
reports/universe.csv and reports/universe.md.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from biss import config  # noqa: E402
from biss.data import binance, weex  # noqa: E402
from biss.universe import classify, binance_symbol_for  # noqa: E402

cfg = config.load()
D = config.data_dir(cfg) / "weex"
(D / "daily").mkdir(parents=True, exist_ok=True)
REP = config.ROOT / "reports"
REP.mkdir(exist_ok=True)


def main() -> None:
    ei = weex.exchange_info()
    rl = weex.risk_limits()
    tk = weex.ticker_24h()
    for name, obj in (("exchange_info", ei), ("risk_limits", rl), ("ticker24h", tk)):
        (D / f"{name}.json").write_text(json.dumps(obj), encoding="utf-8")
    brackets = {x["symbol"]: x["brackets"] for x in rl}
    tick = {x["symbol"]: x for x in tk}

    # Binance symbols (live + delisted, from data.binance.vision) for history mapping
    bn_all = {x for x in binance.list_um_symbols("klines") if x.endswith("USDT")}
    live = binance._get(binance.FAPI + "/fapi/v1/exchangeInfo").json()
    bn_live = {s["symbol"] for s in live["symbols"] if s.get("contractType") == "PERPETUAL" and s["status"] == "TRADING"}
    bn_meta = {s["symbol"]: s for s in live["symbols"]}
    (config.data_dir(cfg) / "binance").mkdir(exist_ok=True)
    (config.data_dir(cfg) / "binance" / "symbols.json").write_text(
        json.dumps({"vision": sorted(bn_all), "live": sorted(bn_live),
                    "underlying": {k: v.get("underlyingType") for k, v in bn_meta.items()},
                    "subtype": {k: v.get("underlyingSubType") for k, v in bn_meta.items()}}), encoding="utf-8")

    syms = ei["symbols"]

    def daily(s: dict) -> tuple[str, pd.DataFrame]:
        try:
            df = weex.klines_recent(s["symbol"], "1d", 1000)
        except Exception as e:  # noqa: BLE001
            print("daily fail", s["symbol"], e)
            df = pd.DataFrame()
        if not df.empty:
            df.to_parquet(D / "daily" / f"{s['symbol']}.parquet")
        return s["symbol"], df

    with ThreadPoolExecutor(8) as ex:
        dailies = dict(ex.map(daily, syms))

    def listing(sym: str) -> pd.Timestamp | None:
        df = dailies.get(sym)
        if df is None or df.empty:
            return None
        if len(df) < 1000:
            return df.index[0]
        try:
            return weex.first_bar(sym, "1d")
        except Exception:  # noqa: BLE001
            return df.index[0]

    with ThreadPoolExecutor(6) as ex:
        listed = dict(zip([s["symbol"] for s in syms], ex.map(listing, [s["symbol"] for s in syms])))

    rows = []
    now = pd.Timestamp.now(tz="UTC").normalize()
    for s in syms:
        sym = s["symbol"]
        cls = classify(s)
        df = dailies.get(sym, pd.DataFrame())
        last30 = df[df.index >= now - pd.Timedelta(days=30)] if not df.empty else df
        b = brackets.get(sym, [])
        bn = binance_symbol_for(s["baseAsset"], cls, bn_all, {k: v.get("underlyingType") for k, v in bn_meta.items()})
        n_settle = len(s.get("delivery") or [])
        rows.append({
            "symbol": sym, "base": s["baseAsset"], "asset_class": cls,
            "weex_underlying_type": s.get("underlyingType"), "sectors": ",".join(s.get("underlyingSubType") or []),
            "listing_date": listed.get(sym).date() if listed.get(sym) is not None else None,
            "weex_daily_bars": len(df),
            "max_leverage": s.get("maxLeverage"), "n_brackets": len(b),
            "bracket1_cap_usd": float(b[0]["notionalCap"]) if b else None,
            "bracket1_mmr": float(b[0]["maintMarginRatio"]) if b else None,
            "tick_size": 10 ** -int(s["pricePrecision"]), "min_size": s.get("minOrderSize"),
            "contract_val": s.get("contractVal"),
            "maker_fee": s.get("makerFeeRate"), "taker_fee": s.get("takerFeeRate"),
            "api_taker_fee": s.get("apiTakerFeeRate"),
            "funding_interval_h": 24 / n_settle if n_settle else None,
            "vol_30d_usd": float(last30["quote_volume"].sum()) if not last30.empty else 0.0,
            "median_daily_vol_30d_usd": float(last30["quote_volume"].median()) if not last30.empty else 0.0,
            "vol_24h_usd": float(tick.get(sym, {}).get("quoteVolume") or 0),
            "binance_symbol": bn, "binance_live": bn in bn_live if bn else False,
        })
    u = pd.DataFrame(rows).sort_values(["asset_class", "vol_30d_usd"], ascending=[True, False])
    u.to_csv(REP / "universe.csv", index=False)
    (D / "brackets.json").write_text(json.dumps(brackets), encoding="utf-8")
    print(u.groupby("asset_class").agg(n=("symbol", "size"), with_binance=("binance_symbol", "count"),
                                       med_vol=("median_daily_vol_30d_usd", "median")))


if __name__ == "__main__":
    main()
