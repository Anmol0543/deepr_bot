import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

def detect_chart_signals(df: pd.DataFrame):
    """
    Evaluates strict quantitative rules for every candle:
    - LONG: Price cross above EMA 50, EMA 50 > EMA 200, RSI between 45 and 68.
    - SHORT: Price cross below EMA 50, EMA 50 < EMA 200, RSI between 32 and 55.
    Calculates dynamic ATR Stop Loss for each trigger.
    """
    signals = []
    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]
        
        if pd.isna(curr.get("ema_50")) or pd.isna(curr.get("ema_200")) or pd.isna(curr.get("rsi")):
            continue

        close = curr["close"]
        ema50 = curr["ema_50"]
        ema200 = curr["ema_200"]
        rsi = curr["rsi"]
        atr = curr["atr"] if pd.notna(curr.get("atr")) else close * 0.01

        # Bullish Trigger
        if (prev["close"] <= prev["ema_50"]) and (close > ema50) and (ema50 > ema200) and (45.0 <= rsi <= 68.0):
            sl = round(close - (1.5 * atr), 4)
            tp1 = round(close + (1.5 * atr), 4)
            tp2 = round(close + (3.0 * atr), 4)
            signals.append({
                "time": curr["time"],
                "type": "LONG",
                "price": curr["low"] * 0.998,
                "text": (
                    f"🟢 <b>LONG CONFIRMED</b><br>"
                    f"Entry: ${close}<br>"
                    f"SL: ${sl} (-1.5 ATR)<br>"
                    f"TP1: ${tp1} (+1.5 ATR)<br>"
                    f"TP2: ${tp2} (+3.0 ATR)<br>"
                    f"RSI: {rsi:.1f}"
                )
            })

        # Bearish Trigger
        elif (prev["close"] >= prev["ema_50"]) and (close < ema50) and (ema50 < ema200) and (32.0 <= rsi <= 55.0):
            sl = round(close + (1.5 * atr), 4)
            tp1 = round(close - (1.5 * atr), 4)
            tp2 = round(close - (3.0 * atr), 4)
            signals.append({
                "time": curr["time"],
                "type": "SHORT",
                "price": curr["high"] * 1.002,
                "text": (
                    f"🔴 <b>SHORT CONFIRMED</b><br>"
                    f"Entry: ${close}<br>"
                    f"SL: ${sl} (+1.5 ATR)<br>"
                    f"TP1: ${tp1} (-1.5 ATR)<br>"
                    f"TP2: ${tp2} (-3.0 ATR)<br>"
                    f"RSI: {rsi:.1f}"
                )
            })
    return signals

def create_interactive_chart(df: pd.DataFrame, symbol: str, timeframe: str, levels: dict = None, heatmap_data: dict = None):
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.8, 0.2]
    )

    # 1. Candlestick Series
    fig.add_trace(
        go.Candlestick(
            x=df["time"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="OHLC",
            increasing_line_color="#10B981", decreasing_line_color="#EF4444"
        ),
        row=1, col=1
    )

    # 2. EMAs
    fig.add_trace(go.Scatter(x=df["time"], y=df["ema_50"], name="EMA 50", line=dict(color="#38BDF8", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["time"], y=df["ema_200"], name="EMA 200", line=dict(color="#F59E0B", width=1.5)), row=1, col=1)

    # 3. Liquidation Heatmap Horizontal Bands
    if heatmap_data:
        max_vol = max(
            [v for _, v in heatmap_data.get("long_pools", [])] +
            [v for _, v in heatmap_data.get("short_pools", [])] + [1.0]
        )

        # Upper Short Liquidation Pools (Yellow/Orange)
        for price_level, vol in heatmap_data.get("short_pools", []):
            opacity = min(0.35, max(0.08, (vol / max_vol) * 0.35))
            fig.add_hrect(
                y0=price_level * 0.9985, y1=price_level * 1.0015,
                fillcolor="#FACC15", opacity=opacity, line_width=0,
                annotation_text=f"🔥 Short Liq Pool (${price_level})",
                annotation_position="top right", annotation_font_size=9,
                annotation_font_color="#FACC15", row=1, col=1
            )

        # Lower Long Liquidation Pools (Purple/Red)
        for price_level, vol in heatmap_data.get("long_pools", []):
            opacity = min(0.35, max(0.08, (vol / max_vol) * 0.35))
            fig.add_hrect(
                y0=price_level * 0.9985, y1=price_level * 1.0015,
                fillcolor="#A855F7", opacity=opacity, line_width=0,
                annotation_text=f"🩸 Long Liq Pool (${price_level})",
                annotation_position="bottom right", annotation_font_size=9,
                annotation_font_color="#A855F7", row=1, col=1
            )

    # 4. Confirmed Signal Markers
    signals = detect_chart_signals(df)
    longs = [s for s in signals if s["type"] == "LONG"]
    shorts = [s for s in signals if s["type"] == "SHORT"]

    if longs:
        fig.add_trace(
            go.Scatter(
                x=[s["time"] for s in longs], y=[s["price"] for s in longs],
                mode="markers+text", name="BUY Signal",
                marker=dict(symbol="triangle-up", size=14, color="#10B981"),
                text=["BUY" for _ in longs], textposition="bottom center",
                textfont=dict(color="#10B981", size=10, family="Consolas"),
                hovertext=[s["text"] for s in longs], hoverinfo="text"
            ),
            row=1, col=1
        )

    if shorts:
        fig.add_trace(
            go.Scatter(
                x=[s["time"] for s in shorts], y=[s["price"] for s in shorts],
                mode="markers+text", name="SELL Signal",
                marker=dict(symbol="triangle-down", size=14, color="#EF4444"),
                text=["SELL" for _ in shorts], textposition="top center",
                textfont=dict(color="#EF4444", size=10, family="Consolas"),
                hovertext=[s["text"] for s in shorts], hoverinfo="text"
            ),
            row=1, col=1
        )

    # 5. Volume Subplot
    colors = ["#10B981" if c >= o else "#EF4444" for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(x=df["time"], y=df["volume"], name="Volume", marker_color=colors, opacity=0.6), row=2, col=1)

    # 6. Active Execution Targets (Entry, SL, TP)
    if levels:
        if levels.get("entry"):
            fig.add_hline(y=levels["entry"], line_dash="dash", line_color="#3B82F6", annotation_text=f" Entry: {levels['entry']}", row=1, col=1)
        if levels.get("stop_loss"):
            fig.add_hline(y=levels["stop_loss"], line_dash="solid", line_color="#EF4444", annotation_text=f" SL: {levels['stop_loss']}", row=1, col=1)
        if levels.get("take_profit_1"):
            fig.add_hline(y=levels["take_profit_1"], line_dash="solid", line_color="#10B981", annotation_text=f" TP1: {levels['take_profit_1']}", row=1, col=1)
        if levels.get("take_profit_2"):
            fig.add_hline(y=levels["take_profit_2"], line_dash="solid", line_color="#059669", annotation_text=f" TP2: {levels['take_profit_2']}", row=1, col=1)

    fig.update_layout(
        title=f"<b>{symbol}</b> • {timeframe.upper()} Candlesticks & Liquidation Heatmap",
        template="plotly_dark", paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
        xaxis_rangeslider_visible=False, height=640,
        margin=dict(l=30, r=60, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#1F2937")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#1F2937")

    return fig