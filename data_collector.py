import ccxt
import requests
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, ADXIndicator
from ta.volatility import AverageTrueRange

class MarketDataEngine:
    def __init__(self):
        self.exchange = ccxt.binance({'enableRateLimit': True})

    def fetch_chart_dataframe(self, symbol: str, timeframe: str = "15m", limit: int = 150):
        """Fetches raw OHLCV bars from Binance and computes EMAs, RSI, and ATR."""
        bars = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["timestamp"], unit="ms")

        # Trend Indicators (EMAs)
        df["ema_50"] = EMAIndicator(close=df["close"], window=50).ema_indicator()
        df["ema_200"] = EMAIndicator(close=df["close"], window=200).ema_indicator()

        # Momentum & Volatility Indicators (RSI & ATR)
        df["rsi"] = RSIIndicator(close=df["close"], window=14).rsi()
        df["atr"] = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14).average_true_range()

        return df

    def calculate_liquidation_heatmap_clusters(self, df: pd.DataFrame, current_price: float):
        """
        Calculates estimated liquidation density bands across standard leverage tiers (25x, 50x, 100x).
        Returns upper short liquidation pools and lower long liquidation pools.
        """
        long_clusters = {}
        short_clusters = {}
        
        recent_df = df.tail(60)
        
        leverage_tiers = [
            (25, 1 / 25),   # 4.0% adverse move
            (50, 1 / 50),   # 2.0% adverse move
            (100, 1 / 100)  # 1.0% adverse move
        ]

        for _, row in recent_df.iterrows():
            vol = row["volume"]
            close = row["close"]

            for lev, pct in leverage_tiers:
                # Long positions: liquidations sit BELOW entry
                long_liq_price = round(close * (1.0 - pct), 1)
                if long_liq_price < current_price:
                    price_bin = round(long_liq_price, -1 if current_price > 500 else 1)
                    long_clusters[price_bin] = long_clusters.get(price_bin, 0.0) + (vol * 0.33)

                # Short positions: liquidations sit ABOVE entry
                short_liq_price = round(close * (1.0 + pct), 1)
                if short_liq_price > current_price:
                    price_bin = round(short_liq_price, -1 if current_price > 500 else 1)
                    short_clusters[price_bin] = short_clusters.get(price_bin, 0.0) + (vol * 0.33)

        sorted_longs = sorted(long_clusters.items(), key=lambda x: x[1], reverse=True)[:4]
        sorted_shorts = sorted(short_clusters.items(), key=lambda x: x[1], reverse=True)[:4]

        return {
            "long_pools": sorted_longs,
            "short_pools": sorted_shorts
        }

    def fetch_single_tf(self, symbol: str, timeframe: str):
        """Fetches OHLCV and calculates RSI, EMAs, ATR, and ADX for trend strength."""
        bars = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
        df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])

        df["rsi"] = RSIIndicator(close=df["close"], window=14).rsi()
        df["ema_50"] = EMAIndicator(close=df["close"], window=50).ema_indicator()
        df["ema_200"] = EMAIndicator(close=df["close"], window=200).ema_indicator()

        atr_ind = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14)
        adx_ind = ADXIndicator(high=df["high"], low=df["low"], close=df["close"], window=14)
        df["atr"] = atr_ind.average_true_range()
        df["adx"] = adx_ind.adx()

        latest = df.iloc[-1]
        adx_val = round(float(latest["adx"]), 2) if pd.notna(latest["adx"]) else 15.0
        atr_val = round(float(latest["atr"]), 4)

        if adx_val < 20:
            regime = "Consolidation / Chop"
        elif adx_val < 35:
            regime = "Trending"
        else:
            regime = "Strong Momentum Trend"

        trend = "Bullish" if latest["close"] > latest["ema_50"] else "Bearish"

        return {
            "timeframe": timeframe,
            "price": round(float(latest["close"]), 4),
            "rsi": round(float(latest["rsi"]), 2) if pd.notna(latest["rsi"]) else 50.0,
            "ema_50": round(float(latest["ema_50"]), 4),
            "ema_200": round(float(latest["ema_200"]), 4),
            "atr": atr_val,
            "adx": adx_val,
            "regime": regime,
            "trend": trend
        }

    def fetch_mtf_indicators(self, symbol="BTC/USDT"):
        """Pulls 15m, 30m, and 1h indicators simultaneously and computes alignment."""
        tf_15m = self.fetch_single_tf(symbol, "15m")
        tf_30m = self.fetch_single_tf(symbol, "30m")
        tf_1h = self.fetch_single_tf(symbol, "1h")

        trends = [tf_15m["trend"], tf_30m["trend"], tf_1h["trend"]]
        bull_count = trends.count("Bullish")

        if bull_count == 3:
            alignment = "Strong Bullish Confluence (All 3 TFs Bullish)"
        elif bull_count == 0:
            alignment = "Strong Bearish Confluence (All 3 TFs Bearish)"
        elif bull_count == 2:
            alignment = "Moderate Bullish (2 of 3 TFs Bullish)"
        else:
            alignment = "Moderate Bearish (2 of 3 TFs Bearish)"

        return {
            "symbol": symbol,
            "current_price": tf_1h["price"],
            "alignment": alignment,
            "atr_1h": tf_1h["atr"],
            "adx_1h": tf_1h["adx"],
            "regime_1h": tf_1h["regime"],
            "15m": tf_15m,
            "30m": tf_30m,
            "1h": tf_1h
        }

    def fetch_derivatives_flow(self, symbol=None):
        """Fetches authentic Binance Futures taker buy/sell ratio and Open Interest delta."""
        if not symbol or "PAXG" in symbol:
            return {
                "funding_rate": "0.0000%",
                "taker_buy_sell_ratio": 1.0,
                "oi_delta": "0.00%",
                "flow_bias": "Spot Only / Neutral"
            }

        try:
            taker_url = f"https://fapi.binance.com/futures/data/takerlongshortRatio?symbol={symbol}&period=15m&limit=2"
            taker_res = requests.get(taker_url, timeout=4).json()
            taker_ratio = float(taker_res[-1]["buySellRatio"]) if taker_res else 1.0

            oi_url = f"https://fapi.binance.com/futures/data/openInterestHist?symbol={symbol}&period=15m&limit=2"
            oi_res = requests.get(oi_url, timeout=4).json()
            if len(oi_res) >= 2:
                prev_oi = float(oi_res[0]["sumOpenInterest"])
                curr_oi = float(oi_res[1]["sumOpenInterest"])
                oi_delta_pct = ((curr_oi - prev_oi) / prev_oi) * 100
            else:
                oi_delta_pct = 0.0

            funding_res = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}", timeout=4).json()
            funding_rate = float(funding_res.get("lastFundingRate", 0)) * 100

            if taker_ratio > 1.15 and oi_delta_pct > 0.5:
                flow_bias = "Bullish Aggressor Accumulation"
            elif taker_ratio < 0.85 and oi_delta_pct > 0.5:
                flow_bias = "Bearish Short Positioning"
            elif taker_ratio < 0.85 and oi_delta_pct < -0.5:
                flow_bias = "Long Capitulation (Exhaustion)"
            elif taker_ratio > 1.15 and oi_delta_pct < -0.5:
                flow_bias = "Short Squeeze (Exhaustion)"
            else:
                flow_bias = "Balanced / Neutral"

            return {
                "funding_rate": f"{funding_rate:.4f}%",
                "taker_buy_sell_ratio": round(taker_ratio, 2),
                "oi_delta": f"{oi_delta_pct:+.2f}%",
                "flow_bias": flow_bias
            }
        except Exception:
            return {
                "funding_rate": "0.0000%",
                "taker_buy_sell_ratio": 1.0,
                "oi_delta": "0.00%",
                "flow_bias": "Neutral"
            }

    def fetch_news(self):
        """Scrapes breaking crypto market headlines from RSS."""
        try:
            url = "https://api.rss2json.com/v1/api.json?rss_url=https://www.coindesk.com/arc/outboundfeeds/rss/"
            res = requests.get(url, timeout=5).json()
            return [item['title'] for item in res.get('items', [])[:3]] or ["Markets steady."]
        except Exception:
            return ["News feed unavailable."]