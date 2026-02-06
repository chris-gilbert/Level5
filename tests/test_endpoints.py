"""Tests for public and SIWS-authenticated proxy endpoints."""

import json

import pytest
from fastapi.testclient import TestClient
from solders.keypair import Keypair

from level5.proxy import database
from level5.proxy.main import app

client = TestClient(app)

# Shared test agent
AGENT = Keypair()
AGENT_PUBKEY = str(AGENT.pubkey())


def _siws_headers(payload: dict):
    """Build SIWS headers by signing the canonical JSON body."""
    message = json.dumps(payload, separators=(",", ":")).encode()
    signature = AGENT.sign_message(message)
    return {
        "X-Agent-Pubkey": AGENT_PUBKEY,
        "X-Agent-Signature": str(signature),
        "X-MOCK-UPSTREAM": "true",
    }, message


@pytest.fixture(autouse=True)
def _fund_agent():
    database.update_balance(AGENT_PUBKEY, 1_000_000, "RESET")


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
    assert "gpt-5.2" in data["pricing"]


# --- Auth required endpoints ---


def test_balance_endpoint_unauthorized():
    response = client.get("/v1/balance")
    assert response.status_code == 401


def test_chat_completions_no_headers():
    payload = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 402


def test_chat_completions_success_and_debit():
    payload = {"model": "gpt-5.2", "messages": [{"role": "user", "content": "hi"}]}
    headers, body = _siws_headers(payload)

    initial_balance = database.get_balance(AGENT_PUBKEY)
    response = client.post("/v1/chat/completions", content=body, headers=headers)

    assert response.status_code == 200
    assert database.get_balance(AGENT_PUBKEY) < initial_balance


def test_messages_success_and_debit():
    payload = {
        "model": "claude-4.5-opus",
        "messages": [{"role": "user", "content": "hi"}],
    }
    headers, body = _siws_headers(payload)

    initial_balance = database.get_balance(AGENT_PUBKEY)
    response = client.post("/v1/messages", content=body, headers=headers)

    assert response.status_code == 200
    assert database.get_balance(AGENT_PUBKEY) < initial_balance


def test_insufficient_balance_returns_402():
    poor_agent = Keypair()
    payload = {"model": "gpt-5.2", "messages": [{"role": "user", "content": "poor"}]}
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = {
        "X-Agent-Pubkey": str(poor_agent.pubkey()),
        "X-Agent-Signature": str(poor_agent.sign_message(body)),
    }

    response = client.post("/v1/chat/completions", content=body, headers=headers)
    assert response.status_code == 402
    assert "Insufficient" in response.json()["error"]
