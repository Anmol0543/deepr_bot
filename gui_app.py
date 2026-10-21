import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import json
import requests

from data_collector import MarketDataEngine
from analyst import get_active_model, GROQ_API_KEY, generate_trade_plan

# Initialize Engine
engine = MarketDataEngine()

WATCHLIST = {
    "BTC": ("BTC/USDT", "BTCUSDT"),
    "ETH": ("ETH/USDT", "ETHUSDT"),
    "SOL": ("SOL/USDT", "SOLUSDT"),
    "XRP": ("XRP/USDT", "XRPUSDT"),
    "PAXG": ("PAXG/USDT", "PAXGUSDT")
}

class DeeeprTraderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Deeepr AI - Quantitative Crypto & Commodity Terminal")
        self.root.geometry("1050x700")
        self.root.configure(bg="#121418")

        self.chat_history = []
        self.live_snapshot = {}

        self.build_ui()
        # Initial background data fetch
        threading.Thread(target=self.refresh_market_data, daemon=True).start()

    def build_ui(self):
        # 1. Header Frame
        header = tk.Frame(self.root, bg="#1a1d24", height=50)
        header.pack(fill="x", padx=10, pady=5)

        title = tk.Label(header, text="DEEEPR AI QUANT TRADING TERMINAL", 
                         font=("Consolas", 14, "bold"), fg="#00FFA3", bg="#1a1d24")
        title.pack(side="left", padx=15, pady=10)

        self.status_lbl = tk.Label(header, text="Ready", font=("Consolas", 10), fg="#8A92A6", bg="#1a1d24")
        self.status_lbl.pack(side="right", padx=15)

        # 2. Main Panes (Left: Live Data/Scanner, Right: Interactive Chat)
        main_pane = tk.PanedWindow(self.root, orient="horizontal", bg="#121418", bd=0, sashwidth=4)
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        # Left Container (Market Watch & Actions)
        left_frame = tk.Frame(main_pane, bg="#1a1d24", width=420)
        main_pane.add(left_frame)

        # Quick Actions Bar
        act_frame = tk.Frame(left_frame, bg="#1a1d24")
        act_frame.pack(fill="x", padx=10, pady=8)

        scan_btn = tk.Button(act_frame, text="⚡ Scan All Setups", font=("Consolas", 10, "bold"),
                             bg="#2b313a", fg="#00FFA3", activebackground="#00FFA3", activeforeground="#121418",
                             bd=0, padx=10, pady=5, cursor="hand2", command=self.on_scan_clicked)
        scan_btn.pack(side="left", padx=2)

        ref_btn = tk.Button(act_frame, text="🔄 Refresh Tickers", font=("Consolas", 10),
                            bg="#2b313a", fg="#E2E8F0", activebackground="#38414e",
                            bd=0, padx=10, pady=5, cursor="hand2", 
                            command=lambda: threading.Thread(target=self.refresh_market_data, daemon=True).start())
        ref_btn.pack(side="left", padx=5)

        # Live Prices / Indicators Table (Treeview)
        tree_frame = tk.Frame(left_frame, bg="#1a1d24")
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#121418", foreground="#E2E8F0", fieldbackground="#121418", font=("Consolas", 9), rowheight=24)
        style.configure("Treeview.Heading", background="#2b313a", foreground="#00FFA3", font=("Consolas", 9, "bold"))

        cols = ("Symbol", "Price", "RSI", "Funding", "Trend")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=8)
        self.tree.heading("Symbol", text="Asset")
        self.tree.heading("Price", text="Price")
        self.tree.heading("RSI", text="RSI 14")
        self.tree.heading("Funding", text="Funding")
        self.tree.heading("Trend", text="Trend")

        self.tree.column("Symbol", width=65, anchor="center")
        self.tree.column("Price", width=95, anchor="e")
        self.tree.column("RSI", width=60, anchor="center")
        self.tree.column("Funding", width=80, anchor="center")
        self.tree.column("Trend", width=90, anchor="center")
        self.tree.pack(fill="both", expand=True)

        # Right Container (Chat & Trade Setup Plans)
        right_frame = tk.Frame(main_pane, bg="#1a1d24")
        main_pane.add(right_frame)

        # Chat Output Display
        self.chat_display = scrolledtext.ScrolledText(right_frame, wrap="word", bg="#121418", fg="#E2E8F0",
                                                      insertbackground="#00FFA3", font=("Consolas", 10), bd=0, padx=10, pady=10)
        self.chat_display.pack(fill="both", expand=True, padx=10, pady=10)
        self.chat_display.tag_config("user", foreground="#38BDF8", font=("Consolas", 10, "bold"))
        self.chat_display.tag_config("bot", foreground="#F8FAFC")
        self.chat_display.tag_config("verdict_long", foreground="#00FFA3", font=("Consolas", 10, "bold"))
        self.chat_display.tag_config("verdict_short", foreground="#F43F5E", font=("Consolas", 10, "bold"))
        self.chat_display.tag_config("system", foreground="#94A3B8", font=("Consolas", 9, "italic"))

        # Chat Input Area
        input_frame = tk.Frame(right_frame, bg="#1a1d24")
        input_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.entry_box = tk.Entry(input_frame, bg="#20242C", fg="#FFFFFF", insertbackground="#00FFA3",
                                  font=("Consolas", 11), bd=0)
        self.entry_box.pack(side="left", fill="both", expand=True, ipady=8, padx=(0, 8))
        self.entry_box.bind("<Return>", lambda event: self.send_message())

        send_btn = tk.Button(input_frame, text="Send", font=("Consolas", 10, "bold"),
                             bg="#00FFA3", fg="#121418", activebackground="#00D284",
                             bd=0, padx=15, cursor="hand2", command=self.send_message)
        send_btn.pack(side="right")

    def set_status(self, text):
        self.status_lbl.config(text=text)

    def refresh_market_data(self):
        self.set_status("Fetching 1H data from Binance...")
        snapshot = {}
        for coin, (spot_sym, perp_sym) in WATCHLIST.items():
            try:
                t = engine.fetch_technical_indicators(symbol=spot_sym, timeframe="1h")
                f = engine.fetch_derivatives_flow(symbol=perp_sym)
                snapshot[coin] = {
                    "price": t["current_price"],
                    "rsi": t["rsi_14"],
                    "trend": "Bull" if "Bullish" in t["trend"] else "Bear",
                    "funding": f.get("funding_rate", "N/A"),
                    "raw_techs": t,
                    "raw_flow": f
                }
            except Exception:
                pass

        self.live_snapshot = snapshot

        # Update Treeview rows safely on main thread
        def update_tree():
            for item in self.tree.get_children():
                self.tree.delete(item)
            for coin, data in self.live_snapshot.items():
                self.tree.insert("", "end", values=(
                    coin,
                    f"${data['price']}",
                    data['rsi'],
                    data['funding'],
                    data['trend']
                ))
            self.set_status("Live market data updated.")

        self.root.after(0, update_tree)

    def append_chat(self, sender, text, tag="bot"):
        self.chat_display.config(state="normal")
        if sender:
            self.chat_display.insert("end", f"\n{sender}: ", tag)
        self.chat_display.insert("end", f"{text}\n")
        self.chat_display.see("end")
        self.chat_display.config(state="disabled")

    def send_message(self):
        msg = self.entry_box.get().strip()
        if not msg:
            return
        self.entry_box.delete(0, "end")
        self.append_chat("You", msg, tag="user")

        threading.Thread(target=self.process_chat, args=(msg,), daemon=True).start()

    def process_chat(self, user_query):
        self.set_status("Deeepr AI analyzing...")
        system_prompt = f"""
You are the Deeepr AI Quantitative Crypto Trading Assistant.
You have access to live 1-hour candles, indicators, and perpetual funding rates:
{json.dumps(self.live_snapshot, indent=2, default=str)}

Respond with quantitative clarity, citing precise levels, RSI, and funding rates.
Keep explanations structured and concise.
"""
        messages = [{"role": "system", "content": system_prompt}] + self.chat_history + [{"role": "user", "content": user_query}]

        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            body = {
                "model": get_active_model(),
                "messages": messages,
                "temperature": 0.2
            }
            res = requests.post(url, headers=headers, json=body)
            if res.status_code == 200:
                reply = res.json()["choices"][0]["message"]["content"]
                self.chat_history.append({"role": "user", "content": user_query})
                self.chat_history.append({"role": "assistant", "content": reply})
                self.root.after(0, lambda: self.append_chat("Deeepr AI", reply, tag="bot"))
            else:
                self.root.after(0, lambda: self.append_chat("System", f"API Error: {res.text}", tag="system"))
        except Exception as e:
            self.root.after(0, lambda: self.append_chat("System", f"Error: {e}", tag="system"))

        self.set_status("Ready")

    def on_scan_clicked(self):
        threading.Thread(target=self.run_full_scanner, daemon=True).start()

    def run_full_scanner(self):
        self.set_status("Scanning watchlist for high-conviction signals...")
        self.root.after(0, lambda: self.append_chat("System", "Starting full quantitative scan across 5 assets...", tag="system"))
        
        macro_news = engine.fetch_news()
        actionable_found = False

        for coin, (spot_sym, perp_sym) in WATCHLIST.items():
            try:
                techs = engine.fetch_technical_indicators(symbol=spot_sym, timeframe="1h")
                flow = engine.fetch_derivatives_flow(symbol=perp_sym)
                plan = generate_trade_plan(techs, flow, macro_news)
                verdict = plan.get("verdict", "WAIT")

                if verdict in ["LONG", "SHORT"]:
                    actionable_found = True
                    details = plan.get("plan", {})
                    card = (
                        f"\n{'='*45}\n"
                        f"🚨 {coin} Setup: {verdict} ({plan.get('confidence_percentage')})\n"
                        f"Rationale: {plan.get('synthesis_summary')}\n"
                        f"Entry Zone: {details.get('entry_zone')}\n"
                        f"Stop Loss : {details.get('stop_loss')}\n"
                        f"Targets   : TP1 {details.get('take_profit_1')} | TP2 {details.get('take_profit_2')}\n"
                        f"R:R Ratio : {details.get('risk_reward_ratio')}\n"
                        f"Invalidate: {details.get('invalidation_rule')}\n"
                        f"{'='*45}"
                    )
                    tag = "verdict_long" if verdict == "LONG" else "verdict_short"
                    self.root.after(0, lambda c=card, t=tag: self.append_chat("Signal", c, tag=t))
            except Exception:
                continue

        if not actionable_found:
            self.root.after(0, lambda: self.append_chat("System", "Scan complete: No trades qualified (all pairs WAIT / neutral).", tag="system"))
            
        self.set_status("Ready")

if __name__ == "__main__":
    root = tk.Tk()
    app = DeeeprTraderGUI(root)
    root.mainloop()