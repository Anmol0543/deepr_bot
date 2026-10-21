import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np


def create_interactive_chart(
    df: pd.DataFrame, 
    heatmap_data: dict = None, 
    show_vwap: bool = True, 
    show_ema: bool = True,
    show_cvd: bool = True
) -> go.Figure:
    """
    Constructs an interactive high-performance candlestick chart with:
    - Main price action canvas
    - Overlaid VWAP and EMA bands
    - Liquidation heatmap horizontal bands / cluster zones
    - Cumulative Volume Delta (CVD) subplot
    """
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            title="Awaiting Market Data...",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117"
        )
        return fig

    # 1. Resolve Time Axis Column
    time_col = "time" if "time" in df.columns else ("datetime" if "datetime" in df.columns else "timestamp")
    x_axis = df[time_col]

    # 2. Setup Subplots: Price Action (row 1) and CVD / Flow (row 2)
    fig = make_subplots(
        rows=2, 
        cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        row_heights=[0.78, 0.22]
    )

    # 3. Candlestick Trace
    fig.add_trace(
        go.Candlestick(
            x=x_axis,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OHLCV",
            increasing_line_color="#00F5A0",
            decreasing_line_color="#FF3366",
            increasing_fillcolor="#00F5A0",
            decreasing_fillcolor="#FF3366",
            opacity=0.9
        ),
        row=1, col=1
    )

    # 4. Moving Average Indicators
    if show_ema:
        if "ema_9" in df.columns:
            fig.add_trace(go.Scatter(x=x_axis, y=df["ema_9"], mode="lines", name="EMA 9", line=dict(color="#00D2FF", width=1.2)), row=1, col=1)
        if "ema_21" in df.columns:
            fig.add_trace(go.Scatter(x=x_axis, y=df["ema_21"], mode="lines", name="EMA 21", line=dict(color="#FCEE21", width=1.2)), row=1, col=1)
        if "ema_50" in df.columns:
            fig.add_trace(go.Scatter(x=x_axis, y=df["ema_50"], mode="lines", name="EMA 50", line=dict(color="#FF8A00", width=1.4)), row=1, col=1)

    # 5. Volume Weighted Average Price (VWAP)
    if show_vwap and "vwap" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=x_axis,
                y=df["vwap"],
                mode="lines",
                name="VWAP",
                line=dict(color="#D946EF", width=1.8, dash="dash")
            ),
            row=1, col=1
        )

    # 6. Cumulative Volume Delta (CVD) Subplot
    if show_cvd and "cvd" in df.columns:
        cvd_color = np.where(df["cvd"] >= 0, "#00F5A0", "#FF3366")
        fig.add_trace(
            go.Bar(
                x=x_axis,
                y=df["cvd"],
                name="CVD Delta",
                marker_color=cvd_color,
                opacity=0.65
            ),
            row=2, col=1
        )

    # 7. Liquidation Heatmap Pools / Horizontal Bands
    if heatmap_data:
        long_pools = []
        short_pools = []

        # Safe extraction whether heatmap_data is a dict or list
        if isinstance(heatmap_data, dict):
            long_pools = heatmap_data.get("long_pools", [])
            short_pools = heatmap_data.get("short_pools", [])
            # Also check if wrapped under 'clusters'
            if not long_pools and not short_pools and "clusters" in heatmap_data:
                for c in heatmap_data["clusters"]:
                    if c.get("side") == "long":
                        long_pools.append([c.get("price", 0), c.get("estimated_volume", 0)])
                    else:
                        short_pools.append([c.get("price", 0), c.get("estimated_volume", 0)])
        elif isinstance(heatmap_data, list):
            for item in heatmap_data:
                if isinstance(item, dict):
                    if item.get("side") == "long":
                        long_pools.append([item.get("price", 0), item.get("estimated_volume", 0)])
                    else:
                        short_pools.append([item.get("price", 0), item.get("estimated_volume", 0)])

        # Max volume normalization for opacity intensity
        all_vols = [v for _, v in long_pools] + [v for _, v in short_pools]
        max_vol = max(all_vols) if all_vols and max(all_vols) > 0 else 1.0

        # Draw Short Liquidation Zones (Above Market Price)
        for price, vol in short_pools:
            alpha = max(0.15, min(0.65, vol / max_vol))
            fig.add_hline(
                y=price,
                line_dash="dot",
                line_color=f"rgba(255, 51, 102, {alpha:.2f})",
                line_width=1.5,
                annotation_text=f"Short Liq ${price:,.1f}",
                annotation_position="top right",
                annotation_font=dict(size=9, color="#FF3366"),
                row=1, col=1
            )

        # Draw Long Liquidation Zones (Below Market Price)
        for price, vol in long_pools:
            alpha = max(0.15, min(0.65, vol / max_vol))
            fig.add_hline(
                y=price,
                line_dash="dot",
                line_color=f"rgba(0, 245, 160, {alpha:.2f})",
                line_width=1.5,
                annotation_text=f"Long Liq ${price:,.1f}",
                annotation_position="bottom right",
                annotation_font=dict(size=9, color="#00F5A0"),
                row=1, col=1
            )

    # 8. Dark Terminal Theme & Layout Styling
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0A0E17",
        plot_bgcolor="#0A0E17",
        margin=dict(l=10, r=60, t=25, b=10),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=10, color="#8F9CAE")
        ),
        font=dict(family="JetBrains Mono, Roboto, monospace", color="#E2E8F0")
    )

    fig.update_yaxes(
        side="right",
        gridcolor="#1E293B",
        zerolinecolor="#334155",
        showgrid=True,
        row=1, col=1
    )
    
    fig.update_yaxes(
        side="right",
        gridcolor="#1E293B",
        zerolinecolor="#334155",
        showgrid=True,
        row=2, col=1,
        title=dict(text="CVD", font=dict(size=9, color="#94A3B8"))
    )

    fig.update_xaxes(
        gridcolor="#1E293B",
        zerolinecolor="#334155",
        showgrid=True,
        type="date"
    )

    return fig