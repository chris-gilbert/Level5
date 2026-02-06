"""End-to-end tests with mocked upstream and UUID token authentication."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from solders.keypair import Keypair

from level5.proxy import database
from level5.proxy.main import app

TEST_AGENT = Keypair()
TEST_PUBKEY = str(TEST_AGENT.pubkey())


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test-key")
    import level5.proxy.main as main_mod

    main_mod.OPENAI_API_KEY = "sk-test-key"
    main_mod.ANTHROPIC_API_KEY = "ant-test-key"


@pytest.fixture(autouse=True)
def _setup_balance_and_token():
    """Fund with USDC and create activated token."""
    database.update_balance(TEST_PUBKEY, database.USDC_MINT, 10_000_000, "INITIAL_DEPOSIT")
    global TEST_TOKEN
    TEST_TOKEN, deposit_code = database.create_api_token()
    database.activate_token(deposit_code, TEST_PUBKEY)


@patch("httpx.AsyncClient.post")
def test_e2e_mimic_flow(mock_post):
    """Test full loop with UUID token auth and mocked upstream."""
    client = TestClient(app)

    mock_response = AsyncMock()
    mock_response.status_code = 200
    response_body = {
        "choices": [{"message": {"role": "assistant", "content": "I am a mock response"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    mock_response.content = json.dumps(response_body).encode()
    mock_response.headers = {"Content-Type": "application/json"}
    mock_post.return_value = mock_response

    payload = {
        "model": "gpt-5.2",
        "messages": [{"role": "user", "content": "Help me, Obi-Wan"}],
    }

    response = client.post(f"/proxy/{TEST_TOKEN}/v1/chat/completions", json=payload)

    assert response.status_code == 200
    assert "mock response" in response.text

    # Expected cost with REAL usage: (100 * 1500/1000) + (50 * 4500/1000) = 150 + 225 = 375
    new_balance = database.get_balance(TEST_PUBKEY, database.USDC_MINT)
    assert new_balance == 10_000_000 - 375


def test_e2e_insufficient_balance():
    """Verify 402 with UUID token auth but zero balance."""
    client = TestClient(app)
    poor_agent = Keypair()
    poor_pubkey = str(poor_agent.pubkey())
    poor_token, poor_deposit = database.create_api_token()
    database.activate_token(poor_deposit, poor_pubkey)

    payload = {
        "model": "gpt-5.2",
        "messages": [{"role": "user", "content": "poor me"}],
    }

    response = client.post(f"/proxy/{poor_token}/v1/chat/completions", json=payload)
    assert response.status_code == 402
    assert "Insufficient" in response.json()["error"]
