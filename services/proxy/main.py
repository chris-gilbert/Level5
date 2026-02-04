import os
import json
import base64
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from services.proxy import database
from solders.pubkey import Pubkey
from solders.signature import Signature

load_dotenv()

app = FastAPI(title="Level5")

# In a real scenario, these would be managed securely
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Pricing per 1k tokens (USDC smallest units)
PRICING = {
    "gpt-5.2": {"input": 1500, "output": 4500}, # GPT-5 era pricing
    "claude-4.5-opus": {"input": 3000, "output": 15000},
}

@app.get("/health")
async def health():
    return {"status": "arena_ready", "agent": "Level5"}

@app.get("/v1/pricing")
async def get_pricing():
    return {"pricing": PRICING, "currency": "USDC/1k tokens"}

@app.get("/v1/balance")
async def get_balance(request: Request):
    # SIWS Verification
    pubkey_str = request.headers.get("X-Agent-Pubkey")
    signature_str = request.headers.get("X-Agent-Signature")
    
    if not pubkey_str or not signature_str:
        raise HTTPException(status_code=401, detail="Unauthorized: X-Agent-Pubkey or X-Agent-Signature missing")
    
    # In a GET request, we might not have a body to sign, 
    # so we could sign the pubkey itself or a timestamp.
    # For now, let's assume the agent signs the pubkey string for the balance check.
    try:
        pubkey = Pubkey.from_string(pubkey_str)
        signature = Signature.from_string(signature_str)
        if not signature.verify(pubkey, pubkey_str.encode()):
            raise HTTPException(status_code=401, detail="Invalid SIWS Signature")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"SIWS Verification Failed: {str(e)}")
    
    balance = database.get_balance(pubkey_str)
    return {"pubkey": pubkey_str, "balance": balance}

@app.post("/v1/chat/completions")
async def openai_proxy(request: Request):
    return await handle_proxy(request, "https://api.openai.com/v1/chat/completions", OPENAI_API_KEY)

@app.post("/v1/messages")
async def anthropic_proxy(request: Request):
    return await handle_proxy(request, "https://api.anthropic.com/v1/messages", ANTHROPIC_API_KEY)

async def handle_proxy(request: Request, upstream_url: str, api_key: str):
    # 1. Auth and Balance Check
    pubkey_str = request.headers.get("X-Agent-Pubkey")
    signature_str = request.headers.get("X-Agent-Signature")
    
    if not pubkey_str or not signature_str:
        return Response(
            content=json.dumps({"error": "Payment Required (X-Agent-Pubkey or X-Agent-Signature missing)"}),
            status_code=402,
            headers={"payment-required": "SIWS_SIGNATURE_REQUIRED", "Content-Type": "application/json"}
        )

    # For proxy requests, we verify the signature of the JSON body
    body_bytes = await request.body()
    try:
        pubkey = Pubkey.from_string(pubkey_str)
        signature = Signature.from_string(signature_str)
        # We need to ensure the body is exactly what was signed (canonical matching bit-for-bit)
        if not signature.verify(pubkey, body_bytes):
            return Response(
                content=json.dumps({"error": "Invalid SIWS Signature"}),
                status_code=401,
                headers={"Content-Type": "application/json"}
            )
    except Exception as e:
        return Response(
            content=json.dumps({"error": f"SIWS Verification Failed: {str(e)}"}),
            status_code=401,
            headers={"Content-Type": "application/json"}
        )

    current_balance = database.get_balance(pubkey_str)
    
    if current_balance <= 0:
        return Response(
            content=json.dumps({"error": "Payment Required: Insufficient Deposit Balance"}),
            status_code=402,
            headers={"Content-Type": "application/json"}
        )

    # 3. Forward to upstream (or mock for testing)
    body = await request.json()
    model = body.get("model", "unknown")
    is_mock = request.headers.get("X-MOCK-UPSTREAM") == "true"
    
    if is_mock:
        # Simulate a successful response for billing verification
        print("MOCK MODE: Simulating successful upstream response.")
        output_data = {"id": "mock-123", "choices": [{"message": {"content": "Sovereign reply."}}]}
        
        # 4. Track usage and charge
        usage = {"input_tokens": 15, "output_tokens": 25}
        pricing = PRICING.get(model, {"input": 5000, "output": 15000})
        cost = (usage["input_tokens"] * pricing["input"] / 1000) + (usage["output_tokens"] * pricing["output"] / 1000)
        
        database.update_balance(pubkey_str, -int(cost), "DEBIT", json.dumps(usage))
        print(f"Charged {int(cost)} units. New balance: {database.get_balance(pubkey_str)}")

        return Response(
            content=json.dumps(output_data),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )

    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="Upstream API key not configured. Check your .env file."
        )

    headers = {
        "Authorization": f"Bearer {api_key}" if "openai" in upstream_url else api_key,
        "x-api-key": api_key if "anthropic" in upstream_url else None,
        "anthropic-version": "2023-06-01" if "anthropic" in upstream_url else None,
        "Content-Type": "application/json"
    }
    headers = {k: v for k, v in headers.items() if v is not None}

    async with httpx.AsyncClient() as client:
        try:
            upstream_response = await client.post(
                upstream_url,
                json=body,
                headers=headers,
                timeout=60.0
            )
            
            # 4. Track usage and charge (Mock logic)
            input_tokens = 10 # Mock
            output_tokens = 20 # Mock
            
            pricing = PRICING.get(model, {"input": 5000, "output": 15000})
            cost = (input_tokens * pricing["input"] / 1000) + (output_tokens * pricing["output"] / 1000)
            
            database.update_balance(pubkey_str, -int(cost), "DEBIT", json.dumps({"input": input_tokens, "output": output_tokens}))
            print(f"Charged {int(cost)} units. New balance: {database.get_balance(pubkey_str)}")

            return Response(
                content=upstream_response.content,
                status_code=upstream_response.status_code,
                headers=dict(upstream_response.headers)
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
