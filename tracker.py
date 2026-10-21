import sqlite3
import datetime

DB_NAME = "trades.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                verdict TEXT,
                entry_price REAL,
                stop_loss REAL,
                tp1 REAL,
                tp2 REAL,
                status TEXT,
                exit_price REAL,
                closed_at TEXT
            )
        """)
        conn.commit()

def record_signal(symbol: str, verdict: str, entry: float, stop: float, tp1: float, tp2: float):
    """Saves a new signal if an identical open setup is not already active."""
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM signals WHERE symbol = ? AND status = 'OPEN'", (symbol,))
        existing = cur.fetchone()
        
        if existing is None and verdict in ["LONG", "SHORT"]:
            cur.execute("""
                INSERT INTO signals (timestamp, symbol, verdict, entry_price, stop_loss, tp1, tp2, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """, (datetime.datetime.now().isoformat(), symbol, verdict, entry, stop, tp1, tp2))
            conn.commit()

def audit_open_signals(current_prices: dict):
    """Evaluates live market prices against open signals to track wins/losses."""
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM signals WHERE status = 'OPEN'")
        open_signals = cur.fetchall()

        for sig in open_signals:
            sym = sig["symbol"]
            curr_p = current_prices.get(sym)
            if not curr_p:
                continue

            status = "OPEN"
            exit_p = None

            if sig["verdict"] == "LONG":
                if curr_p >= sig["tp1"]:
                    status = "WIN (TP1)"
                    exit_p = curr_p
                elif curr_p <= sig["stop_loss"]:
                    status = "LOSS (SL)"
                    exit_p = curr_p
            elif sig["verdict"] == "SHORT":
                if curr_p <= sig["tp1"]:
                    status = "WIN (TP1)"
                    exit_p = curr_p
                elif curr_p >= sig["stop_loss"]:
                    status = "LOSS (SL)"
                    exit_p = curr_p

            if status != "OPEN":
                cur.execute("""
                    UPDATE signals 
                    SET status = ?, exit_price = ?, closed_at = ?
                    WHERE id = ?
                """, (status, exit_p, datetime.datetime.now().isoformat(), sig["id"]))
        conn.commit()

def get_performance_stats():
    """Calculates overall win rate and total audited trades."""
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT status FROM signals WHERE status != 'OPEN'")
        resolved = cur.fetchall()

        if not resolved:
            return {"total": 0, "wins": 0, "losses": 0, "win_rate": "0%"}

        wins = sum(1 for r in resolved if "WIN" in r["status"])
        total = len(resolved)
        rate = (wins / total) * 100

        return {
            "total": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": f"{rate:.1f}%"
        }

def get_all_signals():
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 20")
        return [dict(r) for r in cur.fetchall()]