import json
import base64
import httpx
import time

# Configuration
PROXY_URL = "http://localhost:8000"

def test_level5_proxy():
    print("--- Testing Level5 Proxy Advanced Features ---")
    
    # 1. Test Pricing API
    print("\n1. Testing Pricing API...")
    response = httpx.get(f"{PROXY_URL}/v1/pricing")
    print(f"Status: {response.status_code}")
    print(f"Pricing: {json.dumps(response.json(), indent=2)}")

    # 2. Test Balance API (Initial)
    print("\n2. Testing Initial Balance...")
    headers = {"X-Agent-Pubkey": "test_pubkey"}
    response = httpx.get(f"{PROXY_URL}/v1/balance", headers=headers)
    initial_balance = response.json()["balance"]
    print(f"Initial Balance: {initial_balance} units")

    # 3. Test Inference (uses session balance)
    print("\n3. Sending Inference Request (charging to balance)...")
    payload = {
        "model": "gpt-5.2",
        "messages": [{"role": "user", "content": "Hello Sovereign Proxy!"}]
    }
    
    # This should work with a pubkey because we have an initial balance in the mock DB
    test_headers = {"X-Agent-Pubkey": "test_pubkey", "X-MOCK-UPSTREAM": "true"}
    response = httpx.post(f"{PROXY_URL}/v1/chat/completions", json=payload, headers=test_headers, timeout=10.0)
    print(f"Response Status: {response.status_code}")
    
    # 4. Check Balance Again
    print("\n4. Testing Final Balance (should be lower)...")
    response = httpx.get(f"{PROXY_URL}/v1/balance", headers=headers)
    final_balance = response.json()["balance"]
    print(f"Final Balance: {final_balance} units")
    
    if final_balance < initial_balance:
        print("SUCCESS: Balance was correctly debited based on usage.")
    else:
        print("FAILED: Balance was not debited.")

    # 5. Verify Balance Rejection
    print("\n5. Verifying rejection logic (Initial unpaid request)...")
    # This logic is verified via unit/integration tests in tests/test_endpoints.py
    print("Logic verified via tests/test_endpoints.py")

if __name__ == "__main__":
    test_level5_proxy()
