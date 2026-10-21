import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import json
from data_collector import MarketDataEngine
from analyst import get_active_model, GROQ_API_KEY, generate_trade_plan, analyze_chart_image
from chart_module import create_interactive_chart
from liquidation_engine import fetch_recent_liquidations
from backtester import run_strategy_backtest
import tracker

st.set_page_config(page_title="Deeepr AI Quant Terminal", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .card-long { background-color: #064E3B; padding: 16px; border-radius: 8px; border-left: 5px solid #10B981; margin-bottom: 12px; }
    .card-short { background-color: #4C0519; padding: 16px; border-radius: 8px; border-left: 5px solid #F43F5E; margin-bottom: 12px; }
    .card-wait { background-color: #1F2937; padding: 16px; border-radius: 8px; border-left: 5px solid #EAB308; margin-bottom: 12px; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_engine():
    return MarketDataEngine()

engine = get_engine()

WATCHLIST = {
    "BTC": ("BTC/USDT", "BTCUSDT"),
    "ETH": ("ETH/USDT", "ETHUSDT"),
    "SOL": ("SOL/USDT", "SOLUSDT"),
    "XRP": ("XRP/USDT", "XRPUSDT"),
    "PAXG": ("PAXG/USDT", "PAXGUSDT")
}

st.sidebar.title("⚡ Deeepr Terminal")
st.sidebar.caption("Liquidation Radar • Backtester • Futures Flow")

def fetch_all():
    data = []
    prices = {}
    for coin, (spot_sym, perp_sym) in WATCHLIST.items():
        try:
            mtf = engine.fetch_mtf_indicators(spot_sym)
            flow = engine.fetch_derivatives_flow(perp_sym)
            liq = fetch_recent_liquidations(perp_sym)
            prices[coin] = mtf["current_price"]
            data.append({
                "Asset": coin,
                "Price": f"${mtf['current_price']:,}",
                "1H Regime": f"{mtf['regime_1h']} (ADX {mtf['adx_1h']})",
                "Taker Ratio": flow.get("taker_buy_sell_ratio", 1.0),
                "OI Delta": flow.get("oi_delta", "0%"),
                "Funding": flow.get("funding_rate", "0%"),
                "Liquidation Bias": liq.get("squeeze_bias", "Neutral"),
                "Long Liq ($)": f"${liq.get('long_liq_usd', 0):,}",
                "Short Liq ($)": f"${liq.get('short_liq_usd', 0):,}",
                "Alignment": mtf["alignment"],
                "raw_mtf": mtf,
                "raw_flow": flow,
                "raw_liq": liq,
                "raw_price": mtf["current_price"]
            })
        except Exception:
            pass

    tracker.audit_open_signals(prices)
    return data

tab_chart, tab_matrix, tab_scanner, tab_backtest, tab_ledger, tab_chat = st.tabs([
    "📈 Interactive Chart",
    "📊 MTF & Flow Matrix", 
    "🎯 Quantitative Signals",
    "🧪 Strategy Backtester",
    "🏆 Win-Rate Ledger", 
    "💬 Assistant & Vision"
])

# 1. Live Interactive Chart & Liquidation Heatmap
with tab_chart:
    st.subheader("Interactive Trading Terminal & Liquidation Heatmap")

    c_asset, c_tf, c_live = st.columns([2, 1, 1])
    with c_asset:
        selected_asset = st.selectbox("Asset", list(WATCHLIST.keys()), index=0)
    with c_tf:
        selected_tf = st.selectbox("Timeframe", ["15m", "30m", "1h"], index=0)
    with c_live:
        live_stream = st.checkbox("🟢 Live Stream (10s)", value=True)

    spot_sym, perp_sym = WATCHLIST[selected_asset]

    @st.fragment(run_every=10 if live_stream else None)
    def render_live_chart_pane():
        liq_stats = fetch_recent_liquidations(perp_sym)
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Recent Long Liquidations", f"${liq_stats['long_liq_usd']:,}")
        r2.metric("Recent Short Liquidations", f"${liq_stats['short_liq_usd']:,}")
        r3.metric("Liq Ratio (L / S)", liq_stats["net_ratio"])
        r4.metric("Cascade Status", liq_stats["squeeze_bias"])

        df_candles = engine.fetch_chart_dataframe(spot_sym, timeframe=selected_tf, limit=150)
        curr_price = df_candles.iloc[-1]["close"]
        heatmap_data = engine.calculate_liquidation_heatmap_clusters(df_candles, curr_price)

        active_levels = st.session_state.get("active_plans", {}).get(selected_asset, {}).get("plan")

        fig = create_interactive_chart(
            df_candles,
            spot_sym,
            selected_tf,
            levels=active_levels,
            heatmap_data=heatmap_data
        )
        st.plotly_chart(fig, width="stretch")

    render_live_chart_pane()

# 2. MTF & Flow Matrix
with tab_matrix:
    st.subheader("Market Regimes, Order Flow & Liquidation Aggregation")
    if "market_data" not in st.session_state or st.button("🔄 Refresh Data"):
        with st.spinner("Pulling real-time Binance data..."):
            st.session_state.market_data = fetch_all()

    if "market_data" in st.session_state:
        df = pd.DataFrame(st.session_state.market_data)
        cols = ["Asset", "Price", "1H Regime", "Taker Ratio", "OI Delta", "Liquidation Bias", "Long Liq ($)", "Short Liq ($)", "Alignment"]
        st.dataframe(df[cols], hide_index=True, width="stretch")

# 3. Quantitative Signals
with tab_scanner:
    st.subheader("Actionable Confluence Scanner")
    if "active_plans" not in st.session_state:
        st.session_state.active_plans = {}

    if st.button("⚡ Run Full AI Quantitative Scan", type="primary"):
        if "market_data" not in st.session_state:
            st.session_state.market_data = fetch_all()

        with st.spinner("Synthesizing order flow, liquidation radar, and statistical regimes..."):
            macro_news = engine.fetch_news()
            for item in st.session_state.market_data:
                coin = item["Asset"]
                mtf = item["raw_mtf"]
                flow = item["raw_flow"]

                plan = generate_trade_plan(mtf, flow, macro_news)
                st.session_state.active_plans[coin] = plan
                verdict = plan.get("verdict", "WAIT")
                details = plan.get("plan", {})

                if verdict in ["LONG", "SHORT"] and details:
                    tracker.record_signal(
                        symbol=coin,
                        verdict=verdict,
                        entry=details.get("entry", 0.0),
                        stop=details.get("stop_loss", 0.0),
                        tp1=details.get("take_profit_1", 0.0),
                        tp2=details.get("take_profit_2", 0.0)
                    )

                css_class = "card-long" if verdict == "LONG" else ("card-short" if verdict == "SHORT" else "card-wait")
                emoji = "🟢" if verdict == "LONG" else ("🔴" if verdict == "SHORT" else "🟡")

                st.markdown(f"""
                <div class="{css_class}">
                    <h3>{emoji} {coin}/USDT — {verdict} ({plan.get('confidence_percentage')})</h3>
                    <p><strong>Confluence:</strong> {plan.get('timeframe_confluence')}</p>
                    <p><strong>Rationale:</strong> {plan.get('synthesis_summary')}</p>
                    <p><strong>Entry:</strong> <code>{details.get('entry', 'N/A')}</code> | 
                       <strong>Stop Loss:</strong> <code>{details.get('stop_loss', 'N/A')}</code> | 
                       <strong>R:R:</strong> <code>{details.get('risk_reward_ratio', 'N/A')}</code></p>
                    <p><strong>Targets:</strong> TP1 <code>{details.get('take_profit_1', 'N/A')}</code> | TP2 <code>{details.get('take_profit_2', 'N/A')}</code></p>
                    <p><strong>Invalidation:</strong> <em>{plan.get('invalidation_rule', 'N/A')}</em></p>
                </div>
                """, unsafe_allow_html=True)

# 4. Strategy Backtester
with tab_backtest:
    st.subheader("Historical Strategy Expectancy & Backtest Engine")
    b_col1, b_col2, b_col3 = st.columns(3)
    with b_col1:
        bt_asset = st.selectbox("Select Backtest Asset", list(WATCHLIST.keys()), index=0)
    with b_col2:
        bt_tf = st.selectbox("Backtest Timeframe", ["15m", "30m", "1h"], index=0)
    with b_col3:
        bt_bars = st.slider("Historical Candles to Replay", min_value=100, max_value=500, value=250, step=50)

    if st.button("🧪 Run Historical Simulation", type="primary"):
        with st.spinner(f"Replaying past {bt_bars} candles for {bt_asset}..."):
            hist_df = engine.fetch_chart_dataframe(WATCHLIST[bt_asset][0], timeframe=bt_tf, limit=bt_bars)
            results = run_strategy_backtest(hist_df)

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Win Rate", results["win_rate"])
            m2.metric("Profit Factor", results["profit_factor"])
            m3.metric("Total Return", results["total_pnl_pct"])
            m4.metric("Max Drawdown", results["max_drawdown"])
            m5.metric("Total Trades", results["total_trades"])

            eq_fig = go.Figure()
            eq_fig.add_trace(go.Scatter(y=results["equity_curve"], mode="lines", name="Account Equity ($)", line=dict(color="#10B981", width=2)))
            eq_fig.update_layout(title="Simulated Cumulative Equity Curve ($)", template="plotly_dark", height=380, paper_bgcolor="#0E1117", plot_bgcolor="#0E1117")
            st.plotly_chart(eq_fig, width="stretch")

            if results["trades"]:
                st.write("#### Trade Execution Log")
                st.dataframe(pd.DataFrame(results["trades"]), hide_index=True, width="stretch")

# 5. Win-Rate Ledger
with tab_ledger:
    st.subheader("Live Audited Signal Ledger")
    stats = tracker.get_performance_stats()
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Audited Trades", stats["total"])
    l2.metric("Wins", stats["wins"])
    l3.metric("Losses", stats["losses"])
    l4.metric("Live Hit Rate", stats["win_rate"])

    signals = tracker.get_all_signals()
    if signals:
        st.dataframe(pd.DataFrame(signals), hide_index=True, width="stretch")
    else:
        st.info("No live signals audited yet.")

# 6. Assistant & Vision
with tab_chat:
    st.subheader("Interactive Assistant & Chart Inspector")
    uploaded_chart = st.file_uploader("Upload Chart Screenshot", type=["png", "jpg", "jpeg", "webp"])
    if uploaded_chart:
        st.image(uploaded_chart, caption="Uploaded Chart", width="stretch")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a market question or critique your levels..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                if uploaded_chart:
                    reply = analyze_chart_image(uploaded_chart.getvalue(), prompt, [])
                else:
                    system_prompt = "You are Deeepr AI Quantitative Assistant. Answer sharply based on technical structure."
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
                    body = {
                        "model": get_active_model(),
                        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                        "temperature": 0.2
                    }
                    res = requests.post(url, headers=headers, json=body)
                    reply = res.json()["choices"][0]["message"]["content"]
                st.markdown(reply)
                st.session_state.chat_history.append({"role": "assistant", "content": reply})