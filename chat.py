import json
import requests
from data_collector import MarketDataEngine
from analyst import get_active_model, GROQ_API_KEY

engine = MarketDataEngine()

WATCHLIST = {
    "BTC": ("BTC/USDT", "BTCUSDT"),
    "ETH": ("ETH/USDT", "ETHUSDT"),
    "SOL": ("SOL/USDT", "SOLUSDT"),
    "XRP": ("XRP/USDT", "XRPUSDT"),
    "PAXG": ("PAXG/USDT", "PAXGUSDT")
}

def get_live_market_state():
    """Fetches clean 1H technical indicators and perpetual flow for the watchlist."""
    snapshot = {}
    for coin, (spot_sym, perp_sym) in WATCHLIST.items():
        try:
            techs = engine.fetch_technical_indicators(symbol=spot_sym, timeframe="1h")
            flow = engine.fetch_derivatives_flow(symbol=perp_sym)
            snapshot[coin] = {
                "price": techs["current_price"],
                "rsi_14": techs["rsi_14"],
                "50_ema": techs["ema_50"],
                "200_ema": techs["ema_200"],
                "atr": techs["atr_14"],
                "trend": techs["trend"],
                "volume_cvd": techs["volume_flow"],
                "funding_rate": flow.get("funding_rate", "N/A"),
                "derivatives_bias": flow.get("derivatives_bias", "Neutral")
            }
        except Exception:
            pass
    return snapshot

def ask_analyst(user_query: str, chat_history: list, market_context: dict) -> str:
    system_prompt = f"""
You are the interactive quantitative analyst behind the Deeepr AI trading terminal.
You have direct access to live 1-hour candles, volume delta, funding rates, and trend data.

LIVE 1H MARKET SNAPSHOT:
{json.dumps(market_context, indent=2)}

INSTRUCTIONS:
1. Ground your answers directly in the live numbers shown above (EMAs, RSI, funding rate, CVD).
2. If asked about a specific coin, explain the market structure, key invalidation levels, and whether it's a LONG, SHORT, or WAIT.
3. Be sharp, concise, and quantitative—no generic fluff.
"""

    messages = [{"role": "system", "content": system_prompt}] + chat_history + [{"role": "user", "content": user_query}]

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": get_active_model(),
        "messages": messages,
        "temperature": 0.2
    }

    res = requests.post(url, headers=headers, json=body)
    if res.status_code != 200:
        return f"Groq Error ({res.status_code}): {res.text}"

    return res.json()["choices"][0]["message"]["content"]

def main():
    print("\n" + "="*65)
    print("        DEEEPR AI INTERACTIVE QUANTITATIVE TERMINAL")
    print("="*65)
    print("Fetching live technical snapshot from Binance...")
    market_context = get_live_market_state()
    print("Market data loaded successfully for BTC, ETH, SOL, XRP, and PAXG.\n")
    print("Commands:")
    print("  • Ask anything (e.g. 'Why is ETH short?', 'What is BTC doing?', 'Levels for SOL?')")
    print("  • Type 'refresh' to pull fresh real-time candles")
    print("  • Type 'exit' or 'quit' to close the terminal")
    print("-" * 65 + "\n")

    history = []

    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("\nShutting down terminal. Goodbye!\n")
                break

            if user_input.lower() == "refresh":
                print("Pulling latest market indicators...")
                market_context = get_live_market_state()
                print("Snapshot refreshed.\n")
                continue

            print("\nAnalyzing...", end="", flush=True)
            reply = ask_analyst(user_input, history, market_context)
            print("\r" + " "*20 + "\r", end="")  # Clear 'Analyzing...'

            print(f"Deeepr AI:\n{reply}\n")
            print("-" * 65)

            # Append to rolling conversation memory
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})
            if len(history) > 6:
                history = history[-6:]

        except KeyboardInterrupt:
            print("\nExiting.")
            break

if __name__ == "__main__":
    main()