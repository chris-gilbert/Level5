"""Level5 Sovereign AI Proxy — FastAPI application."""

from __future__ import annotations

import json
import logging
import math
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response

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

# Pricing per 1k tokens (USDC smallest units, 6 decimals)
PRICING: dict[str, dict[str, int]] = {
    "gpt-5.2": {"input": 1500, "output": 4500},
    "claude-4.5-opus": {"input": 3000, "output": 15000},
}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "arena_ready", "agent": "Level5"}


@app.get("/v1/pricing")
async def get_pricing() -> dict[str, Any]:
    return {
        "pricing": PRICING,
        "currency": "USDC",
        "denomination": "smallest units (6 decimals, 1 USDC = 1_000_000)",
        "billing": "USDC-first, SOL fallback at exchange rate",
    }


@app.post("/v1/register")
async def register_agent() -> dict[str, Any]:
    """Register a new agent and get API token + deposit code.

    The deposit_code is used to derive a unique on-chain PDA.
    When the agent deposits to that address, the mirror auto-activates the token.
    """
    api_token, deposit_code = database.create_api_token()

    return {
        "api_token": api_token,
        "deposit_code": deposit_code,
        "base_url": f"https://level5.100x.dev/proxy/{api_token}",
        "status": "pending_deposit",
        "instructions": (
            f"To activate your API token, deposit SOL or USDC on-chain. "
            f"Provide deposit code {deposit_code} when prompted by your wallet or use program: "
            f"C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve"
        ),
    }


@app.get("/proxy/{agent_token}/balance")
async def get_balance(agent_token: str) -> dict[str, Any]:
    """Get agent balance — token resolves to pubkey."""
    pubkey = database.get_pubkey_from_token(agent_token)
    if not pubkey:
        raise HTTPException(status_code=401, detail="Invalid or inactive API token")

    balances = database.get_all_balances(pubkey)
    return {"pubkey": pubkey, "balances": balances}


@app.post("/proxy/{agent_token}/v1/chat/completions")
async def openai_proxy(agent_token: str, request: Request) -> Response:
    pubkey = database.get_pubkey_from_token(agent_token)
    if not pubkey:
        return Response(
            content=json.dumps({"error": "Invalid or inactive API token"}),
            status_code=401,
            headers={"Content-Type": "application/json"},
        )
    return await handle_proxy(
        pubkey, request, "https://api.openai.com/v1/chat/completions", OPENAI_API_KEY
    )


@app.post("/proxy/{agent_token}/v1/messages")
async def anthropic_proxy(agent_token: str, request: Request) -> Response:
    pubkey = database.get_pubkey_from_token(agent_token)
    if not pubkey:
        return Response(
            content=json.dumps({"error": "Invalid or inactive API token"}),
            status_code=401,
            headers={"Content-Type": "application/json"},
        )
    return await handle_proxy(
        pubkey, request, "https://api.anthropic.com/v1/messages", ANTHROPIC_API_KEY
    )


def _calculate_cost_usdc(
    usage: dict[str, int],
    model: str,
) -> int:
    """Calculate cost in USDC smallest units for a given usage."""
    pricing = PRICING.get(model, {"input": 5000, "output": 15000})
    return int(
        usage["input_tokens"] * pricing["input"] / 1000
        + usage["output_tokens"] * pricing["output"] / 1000
    )


def _debit_agent(pubkey: str, cost_usdc: int, usage_json: str) -> str | None:
    """Debit agent using USDC-first, SOL-fallback strategy.

    Returns the token_mint that was debited, or None if insufficient funds.
    """
    # Try USDC first
    usdc_balance = database.get_balance(pubkey, database.USDC_MINT)
    if usdc_balance >= cost_usdc:
        database.update_balance(pubkey, database.USDC_MINT, -cost_usdc, "DEBIT", usage_json)
        return database.USDC_MINT

    # Fallback to SOL — convert cost at exchange rate
    sol_rate = database.get_exchange_rate(database.SOL_MINT)
    if sol_rate > 0:
        # Convert USDC microunits to SOL lamports via exchange rate.
        # USDC has 6 decimals, SOL has 9 → multiply by 1000 / rate.
        cost_sol = math.ceil(cost_usdc * 1000 / sol_rate)
        sol_balance = database.get_balance(pubkey, database.SOL_MINT)
        if sol_balance >= cost_sol:
            database.update_balance(pubkey, database.SOL_MINT, -cost_sol, "DEBIT", usage_json)
            return database.SOL_MINT

    return None


async def handle_proxy(
    agent_pubkey: str,
    request: Request,
    upstream_url: str,
    api_key: str | None,
) -> Response:
    """Check balance, forward to upstream, extract real usage, and debit."""
    # Check if agent has any balance at all
    balances = database.get_all_balances(agent_pubkey)
    total = sum(balances.values())
    if total <= 0:
        return Response(
            content=json.dumps({"error": "Insufficient Deposit Balance"}),
            status_code=402,
            headers={"Content-Type": "application/json"},
        )

    body_bytes = await request.body()
    body = json.loads(body_bytes)
    model = body.get("model", "unknown")
    is_mock = request.headers.get("X-MOCK-UPSTREAM") == "true"

    if is_mock:
        output_data = {
            "id": "mock-123",
            "choices": [{"message": {"content": "Sovereign reply."}}],
        }
        usage = {"input_tokens": 15, "output_tokens": 25}
        cost_usdc = _calculate_cost_usdc(usage, model)
        debited_mint = _debit_agent(agent_pubkey, cost_usdc, json.dumps(usage))
        if not debited_mint:
            return Response(
                content=json.dumps({"error": "Insufficient Deposit Balance"}),
                status_code=402,
                headers={"Content-Type": "application/json"},
            )
        logger.info(
            "Charged %d USDC-equiv from %s",
            cost_usdc,
            debited_mint[:8],
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

            # Extract real usage from upstream response
            resp_data = json.loads(upstream_response.content)
            raw_usage = resp_data.get("usage", {})
            # Normalize: OpenAI uses prompt_tokens/completion_tokens
            # Anthropic uses input_tokens/output_tokens
            usage = {
                "input_tokens": raw_usage.get("input_tokens") or raw_usage.get("prompt_tokens", 0),
                "output_tokens": raw_usage.get("output_tokens")
                or raw_usage.get("completion_tokens", 0),
            }

            cost_usdc = _calculate_cost_usdc(usage, model)
            debited_mint = _debit_agent(agent_pubkey, cost_usdc, json.dumps(usage))
            if debited_mint:
                logger.info(
                    "Charged %d USDC-equiv from %s",
                    cost_usdc,
                    debited_mint[:8],
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
