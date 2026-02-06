"""Tests for the Liquid Mirror on-chain sync."""

import base64
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from level5.proxy import database
from level5.proxy.mirror import LiquidMirror, parse_deposit_account


def _make_deposit_account_data(owner_bytes: bytes, balance: int) -> bytes:
    """Build raw Anchor DepositAccount bytes."""
    discriminator = b"\xd8\x92\x6f\x2a\x5c\x08\x4a\x3e"
    return discriminator + owner_bytes + struct.pack("<Q", balance)


class TestParseDepositAccount:
    def test_valid_account(self):
        owner = bytes(range(32))
        data = _make_deposit_account_data(owner, 500_000)

        result = parse_deposit_account(data)

        assert result is not None
        assert result["balance"] == 500_000
        assert len(result["owner"]) > 0

    def test_too_short(self):
        assert parse_deposit_account(b"short") is None

    def test_zero_balance(self):
        owner = bytes(32)
        data = _make_deposit_account_data(owner, 0)
        result = parse_deposit_account(data)
        assert result is not None
        assert result["balance"] == 0


class TestLiquidMirrorSync:
    def test_sync_balance_deposit(self):
        """Syncing a higher on-chain balance creates a MIRROR_DEPOSIT."""
        mirror = LiquidMirror(rpc_url="http://test", ws_url="ws://test")
        pubkey = "TestPubkey123456789012345678901234567890ab"

        mirror._sync_balance(pubkey, 1_000_000)

        assert database.get_balance(pubkey) == 1_000_000
        history = database.get_transaction_history(pubkey)
        assert len(history) == 1
        assert history[0]["type"] == "MIRROR_DEPOSIT"

    def test_sync_balance_correction(self):
        """Syncing a lower on-chain balance creates a MIRROR_CORRECTION."""
        mirror = LiquidMirror(rpc_url="http://test", ws_url="ws://test")
        pubkey = "TestPubkey123456789012345678901234567890ab"

        database.update_balance(pubkey, 2_000_000, "INITIAL")
        mirror._sync_balance(pubkey, 1_500_000)

        assert database.get_balance(pubkey) == 1_500_000

    def test_sync_no_change(self):
        """No transaction when on-chain matches local."""
        mirror = LiquidMirror(rpc_url="http://test", ws_url="ws://test")
        pubkey = "TestPubkey123456789012345678901234567890ab"

        database.update_balance(pubkey, 1_000_000, "INITIAL")
        mirror._sync_balance(pubkey, 1_000_000)

        history = database.get_transaction_history(pubkey)
        # Only the INITIAL transaction, no MIRROR_*
        assert len(history) == 1
        assert history[0]["type"] == "INITIAL"

    def test_register_account(self):
        mirror = LiquidMirror(rpc_url="http://test", ws_url="ws://test")
        mirror.register_account("acct_addr", "owner_pubkey")
        assert "acct_addr" in mirror._watched_accounts
        assert mirror._watched_accounts["acct_addr"] == "owner_pubkey"


class TestLiquidMirrorPoll:
    @pytest.mark.asyncio
    async def test_poll_all_accounts(self):
        """Poll fetches and syncs watched accounts."""
        owner_bytes = bytes(range(32))
        raw_data = _make_deposit_account_data(owner_bytes, 300_000)
        encoded = base64.b64encode(raw_data).decode()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "value": {
                    "data": [encoded, "base64"],
                    "lamports": 1_000_000,
                }
            }
        }

        mirror = LiquidMirror(rpc_url="http://test", ws_url="ws://test")
        mirror._watched_accounts = {"acct1": "owner1"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            await mirror._poll_all_accounts()

        # Should have synced the parsed owner's balance
        from solders.pubkey import Pubkey

        parsed_owner = str(Pubkey.from_bytes(owner_bytes))
        assert database.get_balance(parsed_owner) == 300_000

    @pytest.mark.asyncio
    async def test_poll_empty_accounts(self):
        """Poll does nothing with no watched accounts."""
        mirror = LiquidMirror(rpc_url="http://test", ws_url="ws://test")
        # No accounts registered - should return without calling RPC
        await mirror._poll_all_accounts()


class TestLiquidMirrorLifecycle:
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """Mirror starts and stops cleanly."""
        mirror = LiquidMirror(rpc_url="http://test", ws_url="ws://test")

        mock_client = AsyncMock()
        mock_client.post.return_value = MagicMock(json=MagicMock(return_value={"result": []}))
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            await mirror.start()

        assert mirror._running is True
        assert len(mirror._tasks) == 2

        await mirror.stop()
        assert mirror._running is False
        assert len(mirror._tasks) == 0


class TestLiquidMirrorDiscover:
    @pytest.mark.asyncio
    async def test_discover_accounts_success(self):
        """Test account discovery via getProgramAccounts."""
        owner_bytes = bytes(range(32))
        raw_data = _make_deposit_account_data(owner_bytes, 750_000)
        encoded = base64.b64encode(raw_data).decode()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "pubkey": "DepositAccountAddr1",
                    "account": {
                        "data": [encoded, "base64"],
                        "lamports": 1_000_000,
                    },
                }
            ]
        }

        mirror = LiquidMirror(rpc_url="http://test", ws_url="ws://test")

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            await mirror._discover_accounts()

        assert len(mirror._watched_accounts) == 1
        assert "DepositAccountAddr1" in mirror._watched_accounts

    @pytest.mark.asyncio
    async def test_discover_accounts_rpc_failure(self):
        """Mirror survives RPC failures gracefully."""
        mirror = LiquidMirror(rpc_url="http://test", ws_url="ws://test")

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("down")
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            await mirror._discover_accounts()

        # No crash, no accounts found
        assert len(mirror._watched_accounts) == 0
