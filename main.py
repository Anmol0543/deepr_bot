import time
from data_collector import MarketDataEngine
from analyst import generate_trade_plan

# Active Watchlist: 4 Cryptos + 1 Commodity (Tokenized Gold)
WATCHLIST = [
    ("BTC/USDT", "BTCUSDT"),
    ("ETH/USDT", "ETHUSDT"),
    ("SOL/USDT", "SOLUSDT"),
    ("XRP/USDT", "XRPUSDT"),
    ("PAXG/USDT", "PAXGUSDT")
]

def scan_markets():
    engine = MarketDataEngine()
    print("\n" + "="*65)
    print("        DEEEPR AI MULTI-ASSET SCANNER (CRYPTO + GOLD)")
    print("="*65)
    
    print("\n[1/2] Fetching macro market news headlines...")
    macro_news = engine.fetch_news()
    for h in macro_news[:2]:
        print(f"  • {h}")

    print(f"\n[2/2] Scanning {len(WATCHLIST)} assets on 1H timeframe...")
    results = []

    for spot_sym, perp_sym in WATCHLIST:
        print(f"  -> Scanning {spot_sym}...", end="", flush=True)
        try:
            techs = engine.fetch_technical_indicators(symbol=spot_sym, timeframe="1h")
            flow = engine.fetch_derivatives_flow(symbol=perp_sym)
            plan = generate_trade_plan(techs, flow, macro_news)
            
            results.append({
                "symbol": spot_sym,
                "price": techs["current_price"],
                "rsi": techs["rsi_14"],
                "funding": flow.get("funding_rate", "N/A"),
                "verdict": plan.get("verdict", "WAIT"),
                "confidence": plan.get("confidence_percentage", "0%"),
                "summary": plan.get("synthesis_summary", ""),
                "trade_plan": plan.get("plan", {})
            })
            print(f" Done ({plan.get('verdict')} - {plan.get('confidence_percentage')})")
        except Exception as e:
            print(f" Error: {e}")
        
        # 1-second pause to respect API rate limits
        time.sleep(1)

    # 1. Overview Table
    print("\n" + "="*68)
    print(f"{'SYMBOL':<11} | {'PRICE':<12} | {'RSI':<6} | {'FUNDING':<10} | {'VERDICT':<7} | {'CONF'}")
    print("-"*68)
    for r in results:
        print(f"{r['symbol']:<11} | {str(r['price']):<12} | {str(r['rsi']):<6} | {r['funding']:<10} | {r['verdict']:<7} | {r['confidence']}")
    print("="*68)

    # 2. Actionable Setups (Filter out WAIT)
    actionable = [r for r in results if r["verdict"] in ["LONG", "SHORT"]]
    
    if not actionable:
        print("\nNo high-conviction trades detected. Market conditions favor WAITING.")
    else:
        print(f"\nFound {len(actionable)} Actionable Setup(s):")
        for item in actionable:
            p = item["trade_plan"]
            print("\n" + "-"*50)
            print(f" Setup: {item['symbol']} -> {item['verdict']} ({item['confidence']})")
            print(f" Rationale  : {item['summary']}")
            print(f" Entry Zone : {p.get('entry_zone')}")
            print(f" Stop Loss  : {p.get('stop_loss')}")
            print(f" TP 1 / TP 2: {p.get('take_profit_1')} / {p.get('take_profit_2')}")
            print(f" R:R Ratio  : {p.get('risk_reward_ratio')}")
            print(f" Invalidate : {p.get('invalidation_rule')}")
            print("-"*50)
            
    print("\nScan completed.\n")

if __name__ == "__main__":
    scan_markets()