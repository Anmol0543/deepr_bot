import os
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from data_collector import MarketDataEngine
from analyst import generate_trade_plan, get_active_model, GROQ_API_KEY

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
engine = MarketDataEngine()

WATCHLIST = [
    ("BTC/USDT", "BTCUSDT"),
    ("ETH/USDT", "ETHUSDT"),
    ("SOL/USDT", "SOLUSDT"),
    ("XRP/USDT", "XRPUSDT"),
    ("PAXG/USDT", "PAXGUSDT")
]

def format_trade_card(symbol: str, plan: dict, techs: dict, flow: dict) -> str:
    verdict = plan.get("verdict", "WAIT")
    confidence = plan.get("confidence_percentage", "N/A")
    summary = plan.get("synthesis_summary", "No details")
    details = plan.get("plan", {})
    
    emoji = "🟢" if verdict == "LONG" else ("🔴" if verdict == "SHORT" else "🟡")
    
    card = (
        f"{emoji} *DEEEPR SETUP: {symbol}*\n"
        f"• *Verdict:* {verdict} ({confidence})\n"
        f"• *Current Price:* `${techs['current_price']}` | *RSI:* `{techs['rsi_14']}`\n"
        f"• *Derivatives Bias:* {flow.get('derivatives_bias', 'Neutral')} ({flow.get('funding_rate', '0%')})\n"
        f"• *Synthesis:* _{summary}_\n\n"
    )
    
    if verdict != "WAIT":
        card += (
            f"📍 *Entry Zone:* `{details.get('entry_zone')}`\n"
            f"🛑 *Stop Loss:* `{details.get('stop_loss')}`\n"
            f"🎯 *Take Profit 1:* `{details.get('take_profit_1')}`\n"
            f"🎯 *Take Profit 2:* `{details.get('take_profit_2')}`\n"
            f"⚖️ *R:R Ratio:* `{details.get('risk_reward_ratio')}`\n"
            f"⚠️ *Invalidation:* `{details.get('invalidation_rule')}`"
        )
    else:
        card += f"⚠️ *Note:* Conflicting or choppy signals. Stay flat.\n• *Invalidation Watch:* `{details.get('invalidation_rule')}`"
    
    return card

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Deeepr AI Trading Assistant Active*\n\n"
        "Available commands:\n"
        "/scan - Scan all 5 watchlist pairs (BTC, ETH, SOL, XRP, PAXG)\n"
        "/btc, /eth, /sol, /xrp, /paxg - Detailed setup for a single asset\n"
        "Or just ask any trading question!"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("⏳ Scanning 1H technicals, perpetual flows, and macro news...")
    
    macro_news = engine.fetch_news()
    actionable_found = False
    
    for spot_sym, perp_sym in WATCHLIST:
        try:
            techs = engine.fetch_technical_indicators(symbol=spot_sym, timeframe="1h")
            flow = engine.fetch_derivatives_flow(symbol=perp_sym)
            plan = generate_trade_plan(techs, flow, macro_news)
            
            if plan.get("verdict") in ["LONG", "SHORT"]:
                actionable_found = True
                card = format_trade_card(spot_sym, plan, techs, flow)
                await update.message.reply_text(card, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            continue
            
    if not actionable_found:
        await update.message.reply_text("📊 Scan complete: All assets are currently in **WAIT / Neutral** regimes.")
        
    await status_msg.delete()

async def single_asset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.replace("/", "").upper()
    mapping = {
        "BTC": ("BTC/USDT", "BTCUSDT"),
        "ETH": ("ETH/USDT", "ETHUSDT"),
        "SOL": ("SOL/USDT", "SOLUSDT"),
        "XRP": ("XRP/USDT", "XRPUSDT"),
        "PAXG": ("PAXG/USDT", "PAXGUSDT")
    }
    
    if cmd not in mapping:
        return
        
    spot_sym, perp_sym = mapping[cmd]
    status_msg = await update.message.reply_text(f"⏳ Generating trade plan for {spot_sym}...")
    
    techs = engine.fetch_technical_indicators(symbol=spot_sym, timeframe="1h")
    flow = engine.fetch_derivatives_flow(symbol=perp_sym)
    news = engine.fetch_news()
    plan = generate_trade_plan(techs, flow, news)
    
    card = format_trade_card(spot_sym, plan, techs, flow)
    await status_msg.delete()
    await update.message.reply_text(card, parse_mode=ParseMode.MARKDOWN)

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    status_msg = await update.message.reply_text("🤔 Analyzing market snapshot...")
    
    snapshot = {}
    for spot_sym, perp_sym in WATCHLIST[:3]:
        try:
            t = engine.fetch_technical_indicators(spot_sym, timeframe="1h")
            f = engine.fetch_derivatives_flow(perp_sym)
            snapshot[spot_sym] = {
                "price": t["current_price"],
                "rsi": t["rsi_14"],
                "trend": t["trend"],
                "funding": f.get("funding_rate", "0%")
            }
        except Exception:
            pass
            
    system_prompt = f"""
You are the Deeepr AI Crypto Quantitative Trading Assistant on Telegram.
Current Snapshot: {snapshot}
Answer user questions concisely using markdown bolding. If asked for recommendations, clarify key technical levels.
"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": get_active_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.3
    }
    
    res = requests.post(url, headers=headers, json=body)
    await status_msg.delete()
    
    if res.status_code == 200:
        reply = res.json()["choices"][0]["message"]["content"]
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text("Error reaching AI engine.")

def main():
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in your .env file.")
        
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    for ticker in ["btc", "eth", "sol", "xrp", "paxg"]:
        app.add_handler(CommandHandler(ticker, single_asset_cmd))
        
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    
    print("Telegram Bot is running. Send /start in Telegram...")
    app.run_polling()

if __name__ == "__main__":
    main()