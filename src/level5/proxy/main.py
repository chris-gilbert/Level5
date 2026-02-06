"""Level5 Sovereign AI Proxy — FastAPI application."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from solders.pubkey import Pubkey
from solders.signature import Signature

from level5.proxy import database
from level5.proxy.mirror import get_mirror

load_dotenv()

logger = logging.getLogger("level5.proxy")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Start/stop the Liquid Mirror on app lifecycle."""
    database.init_db()
    mirror = get_mirror()
    await mirror.start()
    yield
    await mirror.stop()


app = FastAPI(title="Level5", lifespan=lifespan)

# In a real scenario, these would be managed securely
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Pricing per 1k tokens (USDC smallest units)
PRICING: dict[str, dict[str, int]] = {
    "gpt-5.2": {"input": 1500, "output": 4500},
    "claude-4.5-opus": {"input": 3000, "output": 15000},
}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "arena_ready", "agent": "Level5"}


@app.get("/v1/pricing")
async def get_pricing() -> dict[str, Any]:
    return {"pricing": PRICING, "currency": "USDC/1k tokens"}


@app.get("/v1/balance")
async def get_balance(request: Request) -> dict[str, Any]:
    pubkey_str = request.headers.get("X-Agent-Pubkey")
    signature_str = request.headers.get("X-Agent-Signature")

    if not pubkey_str or not signature_str:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: X-Agent-Pubkey or X-Agent-Signature missing",
        )

    try:
        pubkey = Pubkey.from_string(pubkey_str)
        signature = Signature.from_string(signature_str)
        verified = signature.verify(pubkey, pubkey_str.encode())
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=401, detail=f"SIWS Verification Failed: {e!s}") from e

    if not verified:
        raise HTTPException(status_code=401, detail="Invalid SIWS Signature")

    balance = database.get_balance(pubkey_str)
    return {"pubkey": pubkey_str, "balance": balance}


@app.post("/v1/chat/completions")
async def openai_proxy(request: Request) -> Response:
    return await handle_proxy(request, "https://api.openai.com/v1/chat/completions", OPENAI_API_KEY)


@app.post("/v1/messages")
async def anthropic_proxy(request: Request) -> Response:
    return await handle_proxy(request, "https://api.anthropic.com/v1/messages", ANTHROPIC_API_KEY)


async def handle_proxy(
    request: Request,
    upstream_url: str,
    api_key: str | None,
) -> Response:
    """Authenticate, check balance, forward to upstream, and debit."""
    pubkey_str = request.headers.get("X-Agent-Pubkey")
    signature_str = request.headers.get("X-Agent-Signature")

    if not pubkey_str or not signature_str:
        return Response(
            content=json.dumps(
                {"error": "Payment Required (X-Agent-Pubkey or X-Agent-Signature missing)"}
            ),
            status_code=402,
            headers={
                "payment-required": "SIWS_SIGNATURE_REQUIRED",
                "Content-Type": "application/json",
            },
        )

    body_bytes = await request.body()
    try:
        pubkey = Pubkey.from_string(pubkey_str)
        signature = Signature.from_string(signature_str)
        if not signature.verify(pubkey, body_bytes):
            return Response(
                content=json.dumps({"error": "Invalid SIWS Signature"}),
                status_code=401,
                headers={"Content-Type": "application/json"},
            )
    except (ValueError, TypeError) as e:
        return Response(
            content=json.dumps({"error": f"SIWS Verification Failed: {e!s}"}),
            status_code=401,
            headers={"Content-Type": "application/json"},
        )

    current_balance = database.get_balance(pubkey_str)

    if current_balance <= 0:
        return Response(
            content=json.dumps({"error": "Insufficient Deposit Balance"}),
            status_code=402,
            headers={"Content-Type": "application/json"},
        )

    body = await request.json()
    model = body.get("model", "unknown")
    is_mock = request.headers.get("X-MOCK-UPSTREAM") == "true"

    if is_mock:
        output_data = {
            "id": "mock-123",
            "choices": [{"message": {"content": "Sovereign reply."}}],
        }
        usage = {"input_tokens": 15, "output_tokens": 25}
        pricing = PRICING.get(model, {"input": 5000, "output": 15000})
        cost = (
            usage["input_tokens"] * pricing["input"] / 1000
            + usage["output_tokens"] * pricing["output"] / 1000
        )
        database.update_balance(pubkey_str, -int(cost), "DEBIT", json.dumps(usage))
        logger.info(
            "Charged %d units. New balance: %d",
            int(cost),
            database.get_balance(pubkey_str),
        )
        return Response(
            content=json.dumps(output_data),
            status_code=200,
            headers={"Content-Type": "application/json"},
        )

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Upstream API key not configured. Check your .env file.",
        )

    headers = {
        "Content-Type": "application/json",
        **({"Authorization": f"Bearer {api_key}"} if "openai" in upstream_url else {}),
        **(
            {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            if "anthropic" in upstream_url
            else {}
        ),
    }

    async with httpx.AsyncClient() as client:
        try:
            upstream_response = await client.post(
                upstream_url,
                json=body,
                headers=headers,
                timeout=60.0,
            )

            input_tokens = 10
            output_tokens = 20
            pricing = PRICING.get(model, {"input": 5000, "output": 15000})
            cost = input_tokens * pricing["input"] / 1000 + output_tokens * pricing["output"] / 1000
            database.update_balance(
                pubkey_str,
                -int(cost),
                "DEBIT",
                json.dumps({"input": input_tokens, "output": output_tokens}),
            )
            logger.info(
                "Charged %d units. New balance: %d",
                int(cost),
                database.get_balance(pubkey_str),
            )

            return Response(
                content=upstream_response.content,
                status_code=upstream_response.status_code,
                headers=dict(upstream_response.headers),
            )
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e!s}") from e


def main() -> None:
    import uvicorn  # noqa: PLC0415

    uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104


if __name__ == "__main__":
    main()
