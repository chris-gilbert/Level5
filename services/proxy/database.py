import sqlite3
import os
from datetime import datetime

DB_PATH = "sovereign_proxy.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        pubkey TEXT PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_pubkey TEXT,
        type TEXT, -- DEPOSIT or DEBIT
        amount INTEGER,
        usage_json TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (agent_pubkey) REFERENCES agents (pubkey)
    )
    """)
    
    conn.commit()
    conn.close()

def get_balance(pubkey: str) -> int:
    conn = get_db_connection()
    row = conn.execute("SELECT balance FROM agents WHERE pubkey = ?", (pubkey,)).fetchone()
    conn.close()
    return row["balance"] if row else 0

def update_balance(pubkey: str, amount: int, tx_type: str, usage_json: str = None):
    """
    amount is positive for deposits, negative for debits.
    """
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        # Ensure agent exists
        conn.execute("INSERT OR IGNORE INTO agents (pubkey, balance) VALUES (?, 0)", (pubkey,))
        # Update balance
        conn.execute("UPDATE agents SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE pubkey = ?", (amount, pubkey))
        # Log transaction
        conn.execute("INSERT INTO transactions (agent_pubkey, type, amount, usage_json) VALUES (?, ?, ?, ?)", 
                     (pubkey, tx_type, amount, usage_json))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
