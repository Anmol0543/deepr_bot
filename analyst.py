import os
import json
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

PREFERRED_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b"
]

def get_active_model():
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        res = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=5)
        if res.status_code == 200:
            available_ids = {m["id"] for m in res.json().get("data", [])}
            for model_id in PREFERRED_MODELS:
                if model_id in available_ids:
                    return model_id
    except Exception:
        pass
    return "openai/gpt-oss-120b"

def calculate_deterministic_levels(price: float, atr: float, verdict: str):
    """Calculates risk levels based on market volatility (ATR)."""
    atr = max(atr, price * 0.005)  # Fallback to 0.5% if ATR is narrow
    if verdict == "LONG":
        entry = price
        sl = round(entry - (1.5 * atr), 4)
        tp1 = round(entry + (1.5 * atr), 4)
        tp2 = round(entry + (3.0 * atr), 4)
    elif verdict == "SHORT":
        entry = price
        sl = round(entry + (1.5 * atr), 4)
        tp1 = round(entry - (1.5 * atr), 4)
        tp2 = round(entry - (3.0 * atr), 4)
    else:
        return None

    return {
        "entry": entry,
        "stop_loss": sl,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "risk_reward_ratio": "1:2.0"
    }

def generate_trade_plan(mtf_data: dict, derivatives_flow: dict, macro_news: list) -> dict:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    price = mtf_data.get("current_price", 0.0)
    atr = mtf_data.get("atr_1h", 0.0)
    regime = mtf_data.get("regime_1h", "Consolidation / Chop")
    alignment = mtf_data.get("alignment", "")

    # Rule-Based Filtering: Force WAIT during chop or weak ADX
    if regime == "Consolidation / Chop":
        verdict_hint = "WAIT"
    elif "Bullish" in alignment and "Bullish" in derivatives_flow.get("flow_bias", ""):
        verdict_hint = "LONG"
    elif "Bearish" in alignment and "Bearish" in derivatives_flow.get("flow_bias", ""):
        verdict_hint = "SHORT"
    else:
        verdict_hint = "WAIT"

    # Compute deterministic numbers in Python
    calc_plan = calculate_deterministic_levels(price, atr, verdict_hint)

    system_prompt = f"""
You are the Deeepr AI Lead Quantitative Strategist.
Market Regime: {regime} (ADX: {mtf_data.get('adx_1h')})
Calculated Verdict Hint: {verdict_hint}
Calculated Risk Levels: {json.dumps(calc_plan)}

INSTRUCTIONS:
1. Synthesize whether order flow and macro headlines validate this setup.
2. If confirmed, adopt the verdict and keep the exact calculated prices.
3. If risk is elevated, override verdict to WAIT.
4. Output valid JSON only:
{{
  "verdict": "LONG" | "SHORT" | "WAIT",
  "confidence_percentage": "XX%",
  "synthesis_summary": "1-2 sentence core thesis referencing ADX and order flow",
  "invalidation_rule": "Exact price or event invalidating trade"
}}
"""
    body = {
        "model": get_active_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps({"mtf": mtf_data, "flow": derivatives_flow, "news": macro_news})}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }

    try:
        res = requests.post(url, headers=headers, json=body, timeout=15)
        if res.status_code == 200:
            llm_res = json.loads(res.json()["choices"][0]["message"]["content"])
            final_verdict = llm_res.get("verdict", verdict_hint)
            
            # Recalculate if LLM flips verdict
            levels = calculate_deterministic_levels(price, atr, final_verdict) if final_verdict != "WAIT" else {}
            
            return {
                "verdict": final_verdict,
                "confidence_percentage": llm_res.get("confidence_percentage", "70%"),
                "timeframe_confluence": f"{alignment} | ADX: {mtf_data.get('adx_1h')} ({regime})",
                "synthesis_summary": llm_res.get("synthesis_summary", "Confluence confirmed."),
                "invalidation_rule": llm_res.get("invalidation_rule", "Break of 1H EMA 50"),
                "plan": levels
            }
        else:
            return {"verdict": "WAIT", "confidence_percentage": "0%", "synthesis_summary": f"API Error {res.status_code}", "plan": {}}
    except Exception as e:
        return {"verdict": "WAIT", "confidence_percentage": "0%", "synthesis_summary": str(e), "plan": {}}

def analyze_chart_image(image_bytes: bytes, user_query: str, market_context: list) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    base64_img = base64.b64encode(image_bytes).decode("utf-8")
    
    system_prompt = "You are a quantitative technical analyst. Critique drawn support, resistance, and trendlines on this chart."
    content_list = [
        {"type": "text", "text": user_query or "Review my levels on this chart."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}
    ]

    for model_name in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"]:
        body = {
            "model": model_name,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": content_list}],
            "temperature": 0.2
        }
        try:
            res = requests.post(url, headers=headers, json=body, timeout=25)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
        except Exception:
            continue
    return "Unable to process chart image with the vision endpoint."