import pytest
import os
import json
from fastapi.testclient import TestClient
from services.proxy.main import app
from services.proxy import database

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    database.init_db()
    # Reset balance for test agent
    database.update_balance("test_pubkey", 1000000 - database.get_balance("test_pubkey"), "RESET")
    yield

def test_pricing_endpoint():
    """Facet: Structural correctness and expected mock data."""
    response = client.get("/v1/pricing")
    assert response.status_code == 200
    data = response.json()
    assert "pricing" in data
    assert "currency" in data
    assert "gpt-5.2" in data["pricing"]

def test_balance_endpoint_unauthorized():
    """Facet: Authentication requirement."""
    response = client.get("/v1/balance")
    # Current implementation doesn't have auth yet, so this will fail if we want it to be secure
    # For now, let's assume it requires a pubkey header
    assert response.status_code == 401 

def test_balance_endpoint_authorized():
    """Facet: Correct balance retrieval."""
    headers = {"X-Agent-Pubkey": "test_pubkey"}
    response = client.get("/v1/balance", headers=headers)
    assert response.status_code == 200
    assert response.json()["balance"] == 1000000

def test_chat_completions_unauthorized():
    """Facet: Authentication requirement for proxy."""
    payload = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 402 # Payment Required / Base auth check

def test_chat_completions_insufficient_balance():
    """Facet: Insufficient balance handling."""
    # Create agent with 0 balance
    database.init_db()
    database.update_balance("broke_agent", -database.get_balance("broke_agent"), "RESET")
    
    headers = {"X-Agent-Pubkey": "broke_agent"}
    payload = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}
    response = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert response.status_code == 402

def test_chat_completions_success_and_debit():
    """Facet: Successful proxy and balance debit."""
    headers = {"X-Agent-Pubkey": "test_pubkey", "X-MOCK-UPSTREAM": "true"}
    payload = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}
    
    initial_balance = database.get_balance("test_pubkey")
    response = client.post("/v1/chat/completions", json=payload, headers=headers)
    
    assert response.status_code == 200
    final_balance = database.get_balance("test_pubkey")
    assert final_balance < initial_balance

def test_messages_success_and_debit():
    """Facet: Successful Anthropic proxy and balance debit."""
    headers = {"X-Agent-Pubkey": "test_pubkey", "X-MOCK-UPSTREAM": "true"}
    # Anthropic-style payload
    payload = {
        "model": "claude-3-5-sonnet-20240620",
        "messages": [{"role": "user", "content": "hi"}]
    }
    
    initial_balance = database.get_balance("test_pubkey")
    response = client.post("/v1/messages", json=payload, headers=headers)
    
    assert response.status_code == 200
    final_balance = database.get_balance("test_pubkey")
    assert final_balance < initial_balance
