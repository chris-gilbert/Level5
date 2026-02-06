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
def _setup_balance():
    database.update_balance(TEST_PUBKEY, 10_000_000, "INITIAL_DEPOSIT")


def _siws_headers(payload: dict):
    """Generate SIWS headers for the test agent."""
    message = json.dumps(payload, separators=(",", ":")).encode()
    signature = TEST_AGENT.sign_message(message)
    return {
        "X-Agent-Pubkey": TEST_PUBKEY,
        "X-Agent-Signature": str(signature),
    }, message


@patch("httpx.AsyncClient.request")
def test_e2e_mimic_flow(mock_request):
    """Test full loop with SIWS and mocked upstream."""
    client = TestClient(app)

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "I am a mock response"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.content = json.dumps(
        {"choices": [{"message": {"role": "assistant", "content": "I am a mock response"}}]}
    ).encode()
    mock_request.return_value = mock_response

    payload = {
        "model": "gpt-5.2",
        "messages": [{"role": "user", "content": "Help me, Obi-Wan"}],
    }

    headers, message = _siws_headers(payload)

    response = client.post("/v1/chat/completions", content=message, headers=headers)

    assert response.status_code == 200
    assert "mock response" in response.text

    # Expected cost: (10 * 1500/1000) + (20 * 4500/1000) = 15 + 90 = 105
    new_balance = database.get_balance(TEST_PUBKEY)
    assert new_balance == 10_000_000 - 105


def test_e2e_insufficient_balance():
    """Verify 402 with correct SIWS sig but zero balance."""
    client = TestClient(app)
    poor_agent = Keypair()
    poor_pubkey = str(poor_agent.pubkey())

    payload = {"model": "gpt-5.2", "messages": [{"role": "user", "content": "poor me"}]}
    message = json.dumps(payload, separators=(",", ":")).encode()
    headers = {
        "X-Agent-Pubkey": poor_pubkey,
        "X-Agent-Signature": str(poor_agent.sign_message(message)),
    }

    response = client.post("/v1/chat/completions", content=message, headers=headers)
    assert response.status_code == 402
    assert "Insufficient" in response.json()["error"]
