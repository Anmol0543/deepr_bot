import requests
import datetime

def fetch_recent_liquidations(symbol: str = "BTCUSDT", limit: int = 50):
    """
    Fetches recent forced liquidation orders from Binance Futures.
    Computes aggregated long vs short liquidation volumes and detects squeeze regimes.
    """
    if "PAXG" in symbol:
        return {
            "long_liq_usd": 0.0,
            "short_liq_usd": 0.0,
            "net_ratio": 1.0,
            "squeeze_bias": "No Perp Market",
            "recent_wipes": []
        }

    url = f"https://fapi.binance.com/fapi/v1/allForceOrders?symbol={symbol}&limit={limit}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code != 200:
            return {"long_liq_usd": 0.0, "short_liq_usd": 0.0, "net_ratio": 1.0, "squeeze_bias": "Neutral", "recent_wipes": []}
        
        data = res.json()
        long_liq_vol = 0.0
        short_liq_vol = 0.0
        wipes = []

        for item in data:
            side = item.get("side") # SELL = Long liquidated, BUY = Short liquidated
            qty = float(item.get("executedQty", 0))
            price = float(item.get("price", 0))
            usd_value = round(qty * price, 2)
            time_str = datetime.datetime.fromtimestamp(item.get("time", 0) / 1000).strftime("%H:%M:%S")

            if side == "SELL":
                long_liq_vol += usd_value
                wipes.append({"time": time_str, "type": "LONG WIPED", "usd": usd_value, "price": price})
            else:
                short_liq_vol += usd_value
                wipes.append({"time": time_str, "type": "SHORT WIPED", "usd": usd_value, "price": price})

        # Squeeze & Cascade Bias
        total = long_liq_vol + short_liq_vol
        if total > 50000:
            if short_liq_vol > long_liq_vol * 2.5:
                squeeze_bias = "⚠️ Short Squeeze Exhaustion"
            elif long_liq_vol > short_liq_vol * 2.5:
                squeeze_bias = "🩸 Long Cascade (Sweep Bounce Zone)"
            else:
                squeeze_bias = "Active Two-Way Liquidations"
        else:
            squeeze_bias = "Low Liquidation Activity"

        ratio = round(long_liq_vol / (short_liq_vol + 1e-5), 2)

        return {
            "long_liq_usd": round(long_liq_vol, 2),
            "short_liq_usd": round(short_liq_vol, 2),
            "net_ratio": ratio,
            "squeeze_bias": squeeze_bias,
            "recent_wipes": wipes[-8:]
        }
    except Exception:
        return {"long_liq_usd": 0.0, "short_liq_usd": 0.0, "net_ratio": 1.0, "squeeze_bias": "Unavailable", "recent_wipes": []}