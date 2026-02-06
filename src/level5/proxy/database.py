"""SQLite database for sovereign proxy multi-token balance tracking."""

from __future__ import annotations

import os
import sqlite3
import uuid

DB_PATH = "sovereign_proxy.db"

# Well-known token mints
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT_MAINNET = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_MINT_DEVNET = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
USDC_MINT = os.getenv("USDC_MINT", USDC_MINT_DEVNET)

# Default SOL/USDC exchange rate (SOL price in USDC)
DEFAULT_SOL_USDC_RATE = float(os.getenv("SOL_USDC_RATE", "150.0"))


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        pubkey TEXT NOT NULL,
        token_mint TEXT NOT NULL,
        balance INTEGER DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (pubkey, token_mint)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_pubkey TEXT NOT NULL,
        token_mint TEXT NOT NULL,
        type TEXT,
        amount INTEGER,
        usage_json TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (agent_pubkey, token_mint) REFERENCES agents (pubkey, token_mint)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS token_config (
        token_mint TEXT PRIMARY KEY,
        symbol TEXT NOT NULL,
        decimals INTEGER NOT NULL,
        usd_rate REAL NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_tokens (
        api_token TEXT PRIMARY KEY,
        deposit_code TEXT UNIQUE NOT NULL,
        pubkey TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        activated_at DATETIME
    )
    """)

    # Seed default token config
    cursor.execute(
        "INSERT OR IGNORE INTO token_config (token_mint, symbol, decimals, usd_rate)"
        " VALUES (?, 'SOL', 9, ?)",
        (SOL_MINT, DEFAULT_SOL_USDC_RATE),
    )
    cursor.execute(
        "INSERT OR IGNORE INTO token_config (token_mint, symbol, decimals, usd_rate)"
        " VALUES (?, 'USDC', 6, 1.0)",
        (USDC_MINT,),
    )

    conn.commit()
    conn.close()


def get_balance(pubkey: str, token_mint: str = USDC_MINT) -> int:
    """Get balance for a specific token. Defaults to USDC."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT balance FROM agents WHERE pubkey = ? AND token_mint = ?",
        (pubkey, token_mint),
    ).fetchone()
    conn.close()
    return row["balance"] if row else 0


def get_all_balances(pubkey: str) -> dict[str, int]:
    """Get all token balances for an agent."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT token_mint, balance FROM agents WHERE pubkey = ?",
        (pubkey,),
    ).fetchall()
    conn.close()
    return {row["token_mint"]: row["balance"] for row in rows}


def update_balance(
    pubkey: str,
    token_mint: str,
    amount: int,
    tx_type: str,
    usage_json: str | None = None,
) -> None:
    """Update agent balance for a specific token.

    amount is positive for deposits, negative for debits.
    """
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        conn.execute(
            "INSERT OR IGNORE INTO agents (pubkey, token_mint, balance) VALUES (?, ?, 0)",
            (pubkey, token_mint),
        )
        conn.execute(
            "UPDATE agents SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP"
            " WHERE pubkey = ? AND token_mint = ?",
            (amount, pubkey, token_mint),
        )
        conn.execute(
            "INSERT INTO transactions"
            " (agent_pubkey, token_mint, type, amount, usage_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (pubkey, token_mint, tx_type, amount, usage_json),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_transaction_history(
    pubkey: str,
    token_mint: str | None = None,
) -> list[sqlite3.Row]:
    """Get transaction history, optionally filtered by token."""
    conn = get_db_connection()
    if token_mint:
        rows = conn.execute(
            "SELECT * FROM transactions"
            " WHERE agent_pubkey = ? AND token_mint = ?"
            " ORDER BY timestamp DESC",
            (pubkey, token_mint),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE agent_pubkey = ? ORDER BY timestamp DESC",
            (pubkey,),
        ).fetchall()
    conn.close()
    return rows


def get_exchange_rate(token_mint: str) -> float:
    """Get the USD exchange rate for a token. Returns rate or 0.0 if unknown."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT usd_rate FROM token_config WHERE token_mint = ?",
        (token_mint,),
    ).fetchone()
    conn.close()
    return float(row["usd_rate"]) if row else 0.0


def set_exchange_rate(token_mint: str, usd_rate: float) -> None:
    """Update the USD exchange rate for a token."""
    conn = get_db_connection()
    conn.execute(
        "UPDATE token_config SET usd_rate = ?, updated_at = CURRENT_TIMESTAMP WHERE token_mint = ?",
        (usd_rate, token_mint),
    )
    conn.commit()
    conn.close()


def create_api_token() -> tuple[str, str]:
    """Create a new API token and deposit code pair.

    Returns: (api_token: str, deposit_code: str)
    """
    api_token = str(uuid.uuid4())
    deposit_code = uuid.uuid4().hex[:8].upper()  # Short code like ABC123XY

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO api_tokens (api_token, deposit_code) VALUES (?, ?)",
        (api_token, deposit_code),
    )
    conn.commit()
    conn.close()
    return api_token, deposit_code


def activate_token(deposit_code: str, pubkey: str) -> str | None:
    """Activate an API token by linking it to a pubkey.

    Returns the api_token if successful, None if deposit_code not found.
    """
    conn = get_db_connection()
    row = conn.execute(
        "SELECT api_token FROM api_tokens WHERE deposit_code = ?",
        (deposit_code,),
    ).fetchone()

    if not row:
        conn.close()
        return None

    api_token = row["api_token"]
    conn.execute(
        "UPDATE api_tokens SET pubkey = ?, activated_at = CURRENT_TIMESTAMP WHERE deposit_code = ?",
        (pubkey, deposit_code),
    )
    conn.commit()
    conn.close()
    return api_token


def find_pending_token_for_pubkey(pubkey: str) -> str | None:  # noqa: ARG001
    """Check if there's a pending (unactivated) token waiting for this pubkey.

    This is used by the mirror to auto-activate tokens when it sees a new deposit.
    Returns deposit_code if found, None otherwise.

    NOTE: For simplicity, this just returns the oldest pending token.
    In production, you'd use PDA derivation to match deposit_code -> address -> pubkey.
    """
    conn = get_db_connection()
    row = conn.execute(
        "SELECT deposit_code FROM api_tokens WHERE pubkey IS NULL ORDER BY created_at ASC LIMIT 1",
    ).fetchone()
    conn.close()
    return row["deposit_code"] if row else None


def get_pubkey_from_token(api_token: str) -> str | None:
    """Resolve an API token to its linked pubkey.

    Returns pubkey if token is activated, None if invalid or not yet activated.
    """
    conn = get_db_connection()
    row = conn.execute(
        "SELECT pubkey FROM api_tokens WHERE api_token = ?",
        (api_token,),
    ).fetchone()
    conn.close()
    return row["pubkey"] if row and row["pubkey"] else None


if __name__ == "__main__":
    init_db()
