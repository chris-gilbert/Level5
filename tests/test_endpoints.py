"""Tests for public and URL-token-authenticated proxy endpoints."""

import pytest
from fastapi.testclient import TestClient
from solders.keypair import Keypair

from level5.proxy import database
from level5.proxy.main import app

client = TestClient(app)

# Shared test agent
AGENT = Keypair()
AGENT_PUBKEY = str(AGENT.pubkey())


@pytest.fixture(autouse=True)
def _reset_db():
    """Start each test with a clean database."""
    # Fund agent and create activated token for testing
    database.update_balance(AGENT_PUBKEY, database.USDC_MINT, 1_000_000, "RESET")
    # Create and activate a test token
    global TEST_TOKEN
    TEST_TOKEN, deposit_code = database.create_api_token()
    database.activate_token(deposit_code, AGENT_PUBKEY)


# --- Public endpoints (no auth) ---


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "arena_ready"


def test_pricing_endpoint():
    response = client.get("/v1/pricing")
    assert response.status_code == 200
    data = response.json()
    assert "pricing" in data
    assert "currency" in data
    assert data["currency"] == "USDC"
    assert "gpt-5.2" in data["pricing"]


def test_register_endpoint():
    """Registration returns api_token and deposit_code."""
    response = client.post("/v1/register")
    assert response.status_code == 200
    data = response.json()
    assert "api_token" in data
    assert "deposit_code" in data
    assert "base_url" in data
    assert "instructions" in data
    assert data["status"] == "pending_deposit"


# --- URL-token auth endpoints ---


def test_balance_returns_all_tokens():
    """Balance endpoint returns a dict of token balances."""
    # Fund both tokens
    database.update_balance(AGENT_PUBKEY, database.SOL_MINT, 5_000_000, "DEPOSIT")

    response = client.get(f"/proxy/{TEST_TOKEN}/balance")
    assert response.status_code == 200
    data = response.json()
    assert "balances" in data
    assert database.USDC_MINT in data["balances"]
    assert database.SOL_MINT in data["balances"]


def test_balance_invalid_token_returns_401():
    """Invalid token returns 401."""
    response = client.get("/proxy/invalid-uuid-12345/balance")
    assert response.status_code == 401


def test_proxy_invalid_token_returns_401():
    """Invalid API token returns 401."""
    payload = {"model": "gpt-5.2", "messages": [{"role": "user", "content": "hi"}]}
    response = client.post("/proxy/invalid-uuid-12345/v1/chat/completions", json=payload)
    assert response.status_code == 401
    assert "Invalid or inactive" in response.json()["error"]


def test_proxy_unactivated_token_returns_401():
    """Unactivated token (no deposit yet) returns 401."""
    new_token, _deposit_code = database.create_api_token()
    payload = {"model": "gpt-5.2", "messages": [{"role": "user", "content": "hi"}]}
    response = client.post(f"/proxy/{new_token}/v1/chat/completions", json=payload)
    assert response.status_code == 401


def test_chat_completions_success_debits_usdc():
    """USDC-first: debit from USDC when available."""
    payload = {"model": "gpt-5.2", "messages": [{"role": "user", "content": "hi"}]}

    initial = database.get_balance(AGENT_PUBKEY, database.USDC_MINT)
    response = client.post(
        f"/proxy/{TEST_TOKEN}/v1/chat/completions",
        json=payload,
        headers={"X-MOCK-UPSTREAM": "true"},
    )

    assert response.status_code == 200
    assert database.get_balance(AGENT_PUBKEY, database.USDC_MINT) < initial


def test_messages_success_and_debit():
    payload = {
        "model": "claude-4.5-opus",
        "messages": [{"role": "user", "content": "hi"}],
    }

    initial = database.get_balance(AGENT_PUBKEY, database.USDC_MINT)
    response = client.post(
        f"/proxy/{TEST_TOKEN}/v1/messages",
        json=payload,
        headers={"X-MOCK-UPSTREAM": "true"},
    )

    assert response.status_code == 200
    assert database.get_balance(AGENT_PUBKEY, database.USDC_MINT) < initial


def test_sol_fallback_when_usdc_insufficient():
    """SOL fallback: debits SOL when USDC balance is too low."""
    # Set USDC to 0, give SOL instead
    database.update_balance(AGENT_PUBKEY, database.USDC_MINT, -1_000_000, "DRAIN")
    database.update_balance(AGENT_PUBKEY, database.SOL_MINT, 50_000_000_000, "DEPOSIT")

    payload = {"model": "gpt-5.2", "messages": [{"role": "user", "content": "hi"}]}

    initial_sol = database.get_balance(AGENT_PUBKEY, database.SOL_MINT)
    response = client.post(
        f"/proxy/{TEST_TOKEN}/v1/chat/completions",
        json=payload,
        headers={"X-MOCK-UPSTREAM": "true"},
    )

    assert response.status_code == 200
    assert database.get_balance(AGENT_PUBKEY, database.SOL_MINT) < initial_sol


def test_insufficient_balance_returns_402():
    """402 when both USDC and SOL are insufficient."""
    poor_agent = Keypair()
    poor_pubkey = str(poor_agent.pubkey())
    poor_token, poor_deposit = database.create_api_token()
    database.activate_token(poor_deposit, poor_pubkey)

    payload = {"model": "gpt-5.2", "messages": [{"role": "user", "content": "poor"}]}
    response = client.post(f"/proxy/{poor_token}/v1/chat/completions", json=payload)
    assert response.status_code == 402
    assert "Insufficient" in response.json()["error"]
