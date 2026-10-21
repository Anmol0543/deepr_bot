import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, ADXIndicator
from ta.volatility import AverageTrueRange

def run_strategy_backtest(df: pd.DataFrame, initial_balance: float = 10000.0, risk_per_trade_pct: float = 2.0):
    """
    Simulates the MTF rule engine on past candles:
    - Long: EMA 50 > EMA 200, Price cross > EMA 50, RSI 45-68, ADX > 20
    - Short: EMA 50 < EMA 200, Price cross < EMA 50, RSI 32-55, ADX > 20
    - Stop Loss: 1.5 * ATR
    - Take Profit 1: 1.5 * ATR (Takes 50% profit, moves stop to break-even)
    - Take Profit 2: 3.0 * ATR
    """
    df = df.copy()

    # Pre-calculate indicators
    df["ema_50"] = EMAIndicator(close=df["close"], window=50).ema_indicator()
    df["ema_200"] = EMAIndicator(close=df["close"], window=200).ema_indicator()
    df["rsi"] = RSIIndicator(close=df["close"], window=14).rsi()
    df["atr"] = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14).average_true_range()
    df["adx"] = ADXIndicator(high=df["high"], low=df["low"], close=df["close"], window=14).adx()

    balance = initial_balance
    equity_curve = [balance]
    trade_log = []

    active_trade = None

    for i in range(50, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i - 1]

        # Manage active position
        if active_trade is not None:
            pos_type = active_trade["type"]
            entry = active_trade["entry"]
            sl = active_trade["sl"]
            tp1 = active_trade["tp1"]
            tp2 = active_trade["tp2"]
            risk_amt = active_trade["risk_usd"]

            if pos_type == "LONG":
                # Check Stop Loss
                if curr["low"] <= sl:
                    pnl = -risk_amt
                    balance += pnl
                    trade_log.append({
                        "entry_time": active_trade["time"], "exit_time": curr["time"],
                        "type": "LONG", "result": "LOSS (SL)", "pnl": round(pnl, 2), "balance": round(balance, 2)
                    })
                    active_trade = None
                # Check TP2
                elif curr["high"] >= tp2:
                    pnl = risk_amt * 2.0
                    balance += pnl
                    trade_log.append({
                        "entry_time": active_trade["time"], "exit_time": curr["time"],
                        "type": "LONG", "result": "WIN (TP2)", "pnl": round(pnl, 2), "balance": round(balance, 2)
                    })
                    active_trade = None
                # Check TP1 (move SL to break-even)
                elif curr["high"] >= tp1 and active_trade["sl"] < entry:
                    active_trade["sl"] = entry

            elif pos_type == "SHORT":
                if curr["high"] >= sl:
                    pnl = -risk_amt
                    balance += pnl
                    trade_log.append({
                        "entry_time": active_trade["time"], "exit_time": curr["time"],
                        "type": "SHORT", "result": "LOSS (SL)", "pnl": round(pnl, 2), "balance": round(balance, 2)
                    })
                    active_trade = None
                elif curr["low"] <= tp2:
                    pnl = risk_amt * 2.0
                    balance += pnl
                    trade_log.append({
                        "entry_time": active_trade["time"], "exit_time": curr["time"],
                        "type": "SHORT", "result": "WIN (TP2)", "pnl": round(pnl, 2), "balance": round(balance, 2)
                    })
                    active_trade = None
                elif curr["low"] <= tp1 and active_trade["sl"] > entry:
                    active_trade["sl"] = entry

            equity_curve.append(balance)
            continue

        # Look for new entries if no trade active
        close = curr["close"]
        ema50 = curr["ema_50"]
        ema200 = curr["ema_200"]
        rsi = curr["rsi"]
        adx = curr["adx"]
        atr = curr["atr"] if pd.notna(curr["atr"]) else close * 0.01

        risk_usd = balance * (risk_per_trade_pct / 100.0)

        # Long Signal Rule
        if (prev["close"] <= prev["ema_50"]) and (close > ema50) and (ema50 > ema200) and (45.0 <= rsi <= 68.0) and (adx > 20.0):
            active_trade = {
                "time": curr["time"],
                "type": "LONG",
                "entry": close,
                "sl": close - (1.5 * atr),
                "tp1": close + (1.5 * atr),
                "tp2": close + (3.0 * atr),
                "risk_usd": risk_usd
            }

        # Short Signal Rule
        elif (prev["close"] >= prev["ema_50"]) and (close < ema50) and (ema50 < ema200) and (32.0 <= rsi <= 55.0) and (adx > 20.0):
            active_trade = {
                "time": curr["time"],
                "type": "SHORT",
                "entry": close,
                "sl": close + (1.5 * atr),
                "tp1": close - (1.5 * atr),
                "tp2": close - (3.0 * atr),
                "risk_usd": risk_usd
            }

        equity_curve.append(balance)

    # Compute Statistical Metrics
    trades_df = pd.DataFrame(trade_log)
    total_trades = len(trades_df)

    if total_trades > 0:
        wins = trades_df[trades_df["pnl"] > 0]
        losses = trades_df[trades_df["pnl"] < 0]
        win_rate = (len(wins) / total_trades) * 100
        gross_profit = wins["pnl"].sum()
        gross_loss = abs(losses["pnl"].sum())
        profit_factor = round(gross_profit / (gross_loss + 1e-5), 2)
        total_pnl_pct = ((balance - initial_balance) / initial_balance) * 100

        # Max Drawdown
        eq = pd.Series(equity_curve)
        peak = eq.cummax()
        dd = (eq - peak) / peak
        max_dd_pct = round(abs(dd.min()) * 100, 2)
    else:
        win_rate = 0.0
        profit_factor = 0.0
        total_pnl_pct = 0.0
        max_dd_pct = 0.0

    return {
        "final_balance": round(balance, 2),
        "total_pnl_pct": f"{total_pnl_pct:+.2f}%",
        "total_trades": total_trades,
        "win_rate": f"{win_rate:.1f}%",
        "profit_factor": profit_factor,
        "max_drawdown": f"{max_dd_pct:.2f}%",
        "trades": trade_log,
        "equity_curve": equity_curve
    }