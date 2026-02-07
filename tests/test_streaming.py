"""Tests for SSE streaming proxy support."""

import pytest
from fastapi.testclient import TestClient
from solders.keypair import Keypair

from level5.proxy import database
from level5.proxy.main import app

client = TestClient(app)

AGENT = Keypair()
AGENT_PUBKEY = str(AGENT.pubkey())

TEST_TOKEN = ""


@pytest.fixture(autouse=True)
def _reset_db():
    """Start each test with a clean database and funded agent."""
    global TEST_TOKEN
    database.update_balance(AGENT_PUBKEY, database.USDC_MINT, 1_000_000, "RESET")
    TEST_TOKEN, deposit_code = database.create_api_token()
    database.activate_token(deposit_code, AGENT_PUBKEY)


def test_streaming_returns_sse_content_type():
    """Streaming response has text/event-stream content type."""
    payload = {
        "model": "claude-sonnet-4-5-20250929",
        "stream": True,
        "messages": [{"role": "user", "content": "hi"}],
    }
    response = client.post(
        f"/proxy/{TEST_TOKEN}/v1/messages",
        json=payload,
        headers={"X-MOCK-UPSTREAM": "true"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


def test_streaming_anthropic_events():
    """Mock Anthropic streaming returns valid SSE with message_start and message_delta."""
    payload = {
        "model": "claude-sonnet-4-5-20250929",
        "stream": True,
        "messages": [{"role": "user", "content": "hi"}],
    }
    response = client.post(
        f"/proxy/{TEST_TOKEN}/v1/messages",
        json=payload,
        headers={"X-MOCK-UPSTREAM": "true"},
    )
    assert response.status_code == 200
    body = response.text
    assert "event: message_start" in body
    assert "event: message_delta" in body
    assert "Sovereign reply." in body


def test_streaming_debits_after_completion():
    """Balance decrements after consuming a streaming response."""
    initial = database.get_balance(AGENT_PUBKEY, database.USDC_MINT)

    payload = {
        "model": "claude-sonnet-4-5-20250929",
        "stream": True,
        "messages": [{"role": "user", "content": "hi"}],
    }
    response = client.post(
        f"/proxy/{TEST_TOKEN}/v1/messages",
        json=payload,
        headers={"X-MOCK-UPSTREAM": "true"},
    )
    assert response.status_code == 200

    final = database.get_balance(AGENT_PUBKEY, database.USDC_MINT)
    assert final < initial


def test_streaming_402_insufficient_balance():
    """Zero-balance agent gets 402 before streaming starts."""
    poor_agent = Keypair()
    poor_pubkey = str(poor_agent.pubkey())
    poor_token, poor_deposit = database.create_api_token()
    database.activate_token(poor_deposit, poor_pubkey)

    payload = {
        "model": "claude-sonnet-4-5-20250929",
        "stream": True,
        "messages": [{"role": "user", "content": "hi"}],
    }
    response = client.post(
        f"/proxy/{poor_token}/v1/messages",
        json=payload,
    )
    assert response.status_code == 402
    assert "Insufficient" in response.json()["error"]


def test_non_streaming_still_works():
    """Non-streaming (stream: false) returns normal JSON response."""
    payload = {
        "model": "claude-sonnet-4-5-20250929",
        "stream": False,
        "messages": [{"role": "user", "content": "hi"}],
    }
    response = client.post(
        f"/proxy/{TEST_TOKEN}/v1/messages",
        json=payload,
        headers={"X-MOCK-UPSTREAM": "true"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "choices" in data


def test_streaming_openai_events():
    """OpenAI-format SSE via chat/completions endpoint."""
    payload = {
        "model": "gpt-4o",
        "stream": True,
        "messages": [{"role": "user", "content": "hi"}],
    }
    response = client.post(
        f"/proxy/{TEST_TOKEN}/v1/chat/completions",
        json=payload,
        headers={"X-MOCK-UPSTREAM": "true"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "data: " in body
    assert "[DONE]" in body
    assert "Sovereign " in body
