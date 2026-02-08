"""Liquid Mirror: On-chain Solana state synced to local SQLite for zero-latency reads.

Uses Helius RPC (polling) and WebSocket (real-time push) to keep the local
balance database in sync with on-chain deposit accounts.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import struct
from contextlib import suppress
from datetime import datetime, timezone

import httpx
import websockets
from solders.pubkey import Pubkey

from level5.proxy import database

logger = logging.getLogger("level5.mirror")

# Helius configuration
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")
HELIUS_RPC_URL = os.getenv(
    "HELIUS_RPC_URL",
    f"https://devnet.helius-rpc.com/?api-key={HELIUS_API_KEY}",
)
HELIUS_WS_URL = os.getenv(
    "HELIUS_WS_URL",
    f"wss://devnet.helius-rpc.com/?api-key={HELIUS_API_KEY}",
)

# Anchor account discriminator for DepositAccount (first 8 bytes)
DEPOSIT_ACCOUNT_DISCRIMINATOR = b"\xd8\x92\x6f\x2a\x5c\x08\x4a\x3e"

# Account layout sizes
# Legacy (SOL-only): discriminator(8) + owner(32) + balance(8) = 48
DEPOSIT_ACCOUNT_LEGACY_SIZE = 48
# V2 (multi-token): discriminator(8) + owner(32) + mint(32) + balance(8) = 80
DEPOSIT_ACCOUNT_V2_SIZE = 80
# V3 (with deposit_code): disc(8) + owner(32) + mint(32) + code(8) + balance(8) = 88
DEPOSIT_ACCOUNT_V3_SIZE = 88

# Polling interval in seconds (fallback when WebSocket is down)
POLL_INTERVAL = 5.0

# Maximum backoff for reconnection attempts
MAX_BACKOFF = 60.0

# SQLite INTEGER is signed 64-bit; reject parsed balances above this.
MAX_SQLITE_INTEGER = (1 << 63) - 1


def parse_deposit_account(data: bytes) -> dict | None:
    """Parse an Anchor DepositAccount from raw account data.

    Supports three layouts:
        Legacy (48 bytes): discriminator(8) + owner(32) + balance(8)
            → assumes SOL_MINT, no deposit_code
        V2 (80 bytes): discriminator(8) + owner(32) + mint(32) + balance(8)
            → reads mint, no deposit_code
        V3 (88 bytes): discriminator(8) + owner(32) + mint(32) + deposit_code(8) + balance(8)
            → reads mint and deposit_code
    """
    if len(data) < DEPOSIT_ACCOUNT_LEGACY_SIZE:
        return None

    owner_bytes = data[8:40]
    owner = str(Pubkey.from_bytes(owner_bytes))

    if len(data) >= DEPOSIT_ACCOUNT_V3_SIZE:
        # V3 layout: owner + mint + deposit_code + balance
        mint_bytes = data[40:72]
        mint = str(Pubkey.from_bytes(mint_bytes))
        deposit_code = data[72:80].decode("utf-8", errors="replace").rstrip("\x00")
        balance = struct.unpack_from("<Q", data, 80)[0]
    elif len(data) >= DEPOSIT_ACCOUNT_V2_SIZE:
        # V2 layout: owner + mint + balance (no deposit_code)
        mint_bytes = data[40:72]
        mint = str(Pubkey.from_bytes(mint_bytes))
        deposit_code = ""
        balance = struct.unpack_from("<Q", data, 72)[0]
    else:
        # Legacy layout: owner + balance (assume SOL)
        mint = database.SOL_MINT
        deposit_code = ""
        balance = struct.unpack_from("<Q", data, 40)[0]

    if balance > MAX_SQLITE_INTEGER:
        logger.warning("Rejecting account %s: balance %d exceeds max", owner[:8], balance)
        return None

    return {"owner": owner, "mint": mint, "deposit_code": deposit_code, "balance": balance}


class LiquidMirror:
    """Bridges on-chain Solana deposit accounts to local SQLite."""

    def __init__(
        self,
        rpc_url: str = HELIUS_RPC_URL,
        ws_url: str = HELIUS_WS_URL,
        program_id: str | None = None,
    ) -> None:
        self.rpc_url = rpc_url
        self.ws_url = ws_url
        self.program_id = program_id or os.getenv(
            "SOVEREIGN_CONTRACT_ADDRESS",
            "C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve",
        )
        self._watched_accounts: dict[str, str] = {}  # account_addr -> owner_pubkey
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the mirror sync workers."""
        self._running = True
        database.init_db()
        logger.info(
            "Liquid Mirror starting | rpc=%s | program=%s",
            self.rpc_url.split("?")[0],
            self.program_id,
        )

        # Discover existing deposit accounts on startup
        await self._discover_accounts()

        # Launch background workers
        self._tasks = [
            asyncio.create_task(self._poll_loop()),
            asyncio.create_task(self._ws_loop()),
        ]

    async def stop(self) -> None:
        """Gracefully stop the mirror."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()
        logger.info("Liquid Mirror stopped")

    async def _discover_accounts(self) -> None:
        """Discover all deposit accounts owned by the sovereign contract."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getProgramAccounts",
                        "params": [
                            self.program_id,
                            {"encoding": "base64", "commitment": "confirmed"},
                        ],
                    },
                    timeout=30.0,
                )
                result = resp.json()

            accounts = result.get("result", [])
            for acct in accounts:
                pubkey = acct["pubkey"]
                raw_data = base64.b64decode(acct["account"]["data"][0])
                parsed = parse_deposit_account(raw_data)
                if parsed:
                    self._watched_accounts[pubkey] = parsed["owner"]
                    self._sync_balance(
                        parsed["owner"],
                        parsed["mint"],
                        parsed["balance"],
                        parsed["deposit_code"],
                    )

            logger.info("Discovered %d deposit accounts", len(self._watched_accounts))

        except Exception:
            logger.exception("Failed to discover accounts")

    async def _poll_loop(self) -> None:  # pragma: no cover
        """Periodically discover new accounts and poll all watched accounts."""
        backoff = POLL_INTERVAL
        poll_count = 0
        while self._running:
            try:
                # Re-discover new accounts every 6th poll (~30s)
                poll_count += 1
                if poll_count % 6 == 0:
                    await self._discover_accounts()
                await self._poll_all_accounts()
                backoff = POLL_INTERVAL
            except Exception:
                logger.exception("Poll error, backing off %.1fs", backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
            await asyncio.sleep(backoff)

    async def _poll_all_accounts(self) -> None:
        """Fetch current state of all watched deposit accounts."""
        if not self._watched_accounts:
            return

        async with httpx.AsyncClient() as client:
            for account_addr, _owner in list(self._watched_accounts.items()):
                resp = await client.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getAccountInfo",
                        "params": [
                            account_addr,
                            {"encoding": "base64", "commitment": "confirmed"},
                        ],
                    },
                    timeout=10.0,
                )
                result = resp.json()
                value = result.get("result", {}).get("value")
                if value and value.get("data"):
                    raw_data = base64.b64decode(value["data"][0])
                    parsed = parse_deposit_account(raw_data)
                    if parsed:
                        self._sync_balance(
                            parsed["owner"],
                            parsed["mint"],
                            parsed["balance"],
                            parsed["deposit_code"],
                        )

    async def _ws_loop(self) -> None:  # pragma: no cover
        """Subscribe to account changes via Helius WebSocket."""
        backoff = 1.0
        while self._running:
            try:
                await self._ws_subscribe()
                backoff = 1.0  # Reset on success
            except (TimeoutError, asyncio.TimeoutError):
                logger.debug("WebSocket idle timeout, reconnecting")
                backoff = 1.0
            except Exception:
                logger.exception("WebSocket error, reconnecting in %.1fs", backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
            if self._running:
                await asyncio.sleep(backoff)

    async def _ws_subscribe(self) -> None:  # pragma: no cover
        """Connect to Helius WebSocket and listen for account changes."""
        if not self._watched_accounts:
            await asyncio.sleep(POLL_INTERVAL)
            return

        async with websockets.connect(self.ws_url) as ws:
            logger.info("WebSocket connected to %s", self.ws_url.split("?")[0])

            # Subscribe to each watched account
            sub_ids: dict[int, str] = {}
            for idx, (account_addr, _owner) in enumerate(self._watched_accounts.items()):
                await ws.send(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": idx + 1,
                            "method": "accountSubscribe",
                            "params": [
                                account_addr,
                                {"encoding": "base64", "commitment": "confirmed"},
                            ],
                        }
                    )
                )
                # Read subscription confirmation
                confirm = json.loads(await ws.recv())
                if "result" in confirm:
                    sub_ids[confirm["result"]] = account_addr
                    logger.debug(
                        "Subscribed to %s (sub_id=%d)",
                        account_addr,
                        confirm["result"],
                    )

            # Listen for notifications
            while self._running:
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60.0))
                except (TimeoutError, asyncio.TimeoutError):
                    # Idle connection — send a ping to keep it alive
                    await ws.ping()
                    continue
                if msg.get("method") == "accountNotification":
                    params = msg["params"]
                    sub_id = params.get("subscription")
                    account_addr = sub_ids.get(sub_id)
                    if account_addr:
                        value = params["result"]["value"]
                        if value and value.get("data"):
                            raw_data = base64.b64decode(value["data"][0])
                            parsed = parse_deposit_account(raw_data)
                            if parsed:
                                self._sync_balance(
                                    parsed["owner"],
                                    parsed["mint"],
                                    parsed["balance"],
                                    parsed["deposit_code"],
                                )
                                logger.info(
                                    "WS update: %s mint=%s balance=%d",
                                    parsed["owner"][:8],
                                    parsed["mint"][:8],
                                    parsed["balance"],
                                )

    def _sync_balance(
        self,
        owner_pubkey: str,
        token_mint: str,
        on_chain_balance: int,
        deposit_code: str = "",
    ) -> None:
        """Sync an on-chain balance to local SQLite for a specific token.

        On first deposit (delta > 0), auto-activates any pending API token.
        """
        current = database.get_balance(owner_pubkey, token_mint)
        delta = on_chain_balance - current

        # Auto-activate pending tokens on first deposit
        if delta > 0 and current == 0 and deposit_code:
            api_token = database.activate_token(deposit_code, owner_pubkey)
            if api_token:
                logger.info(
                    "Auto-activated token %s for deposit_code %s (pubkey %s)",
                    api_token[:8],
                    deposit_code,
                    owner_pubkey[:8],
                )

        if delta != 0:
            tx_type = "MIRROR_DEPOSIT" if delta > 0 else "MIRROR_CORRECTION"
            database.update_balance(
                owner_pubkey,
                token_mint,
                delta,
                tx_type,
                json.dumps(
                    {
                        "on_chain_balance": on_chain_balance,
                        "local_balance_before": current,
                        "synced_at": datetime.now(tz=timezone.utc).isoformat(),
                    }
                ),
            )
            logger.info(
                "Synced %s [%s]: %d -> %d (%s%d)",
                owner_pubkey[:8],
                token_mint[:8],
                current,
                on_chain_balance,
                "+" if delta > 0 else "",
                delta,
            )

    def register_account(self, account_addr: str, owner_pubkey: str) -> None:
        """Register a new deposit account to watch."""
        self._watched_accounts[account_addr] = owner_pubkey
        logger.info("Watching account %s (owner: %s)", account_addr[:8], owner_pubkey[:8])


# Singleton for FastAPI lifespan
_mirror: LiquidMirror | None = None


def get_mirror() -> LiquidMirror:
    """Get or create the global LiquidMirror instance."""
    global _mirror  # noqa: PLW0603
    if _mirror is None:
        _mirror = LiquidMirror()
    return _mirror
