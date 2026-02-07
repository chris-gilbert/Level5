"""Level5 Budget Management for AI Agents — FastAPI application."""

from __future__ import annotations

import contextlib
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
from fastapi.responses import StreamingResponse

from level5.proxy import database
from level5.proxy.mirror import get_mirror

load_dotenv()

logger = logging.getLogger("level5.proxy")

# Timeout tuned for streaming — long reads for LLM generation
UPSTREAM_TIMEOUT = httpx.Timeout(connect=10, read=300, write=10, pool=10)


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
    # Anthropic models
    "claude-sonnet-4-5-20250929": {"input": 3000, "output": 15000},
    "claude-opus-4-6": {"input": 15000, "output": 75000},
    "claude-3-5-haiku-20241022": {"input": 800, "output": 4000},
    # OpenAI models
    "gpt-4o": {"input": 2500, "output": 10000},
    # Legacy aliases (backward compat)
    "gpt-5.2": {"input": 1500, "output": 4500},
    "claude-4.5-opus": {"input": 3000, "output": 15000},
}

DEFAULT_PRICING = {"input": 5000, "output": 15000}


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
        "base_url": f"https://api.level5.cloud/proxy/{api_token}",
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


@app.get("/v1/admin/stats")
async def admin_stats() -> dict[str, Any]:
    """Revenue and usage statistics for the proxy operator."""
    conn = database.get_db_connection()
    try:
        # Total deposits
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total"
            " FROM transactions WHERE type = 'MIRROR_DEPOSIT'",
        ).fetchone()
        total_deposits = row["total"]

        # Total debits
        row = conn.execute(
            "SELECT COALESCE(SUM(ABS(amount)), 0) AS total FROM transactions WHERE type = 'DEBIT'",
        ).fetchone()
        total_debits = row["total"]

        # Active agents (have at least one positive balance)
        row = conn.execute(
            "SELECT COUNT(DISTINCT pubkey) AS cnt FROM agents WHERE balance > 0",
        ).fetchone()
        active_agents = row["cnt"]

        # Total agents registered
        row = conn.execute("SELECT COUNT(*) AS cnt FROM api_tokens").fetchone()
        registered_tokens = row["cnt"]

        return {
            "total_deposits": total_deposits,
            "total_debits": total_debits,
            "net_revenue": total_debits,
            "active_agents": active_agents,
            "registered_tokens": registered_tokens,
        }
    finally:
        conn.close()


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
    pricing = PRICING.get(model, DEFAULT_PRICING)
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


def _build_upstream_headers(
    upstream_url: str,
    api_key: str,
    request: Request,
) -> dict[str, str]:
    """Build headers for the upstream API call."""
    headers: dict[str, str] = {"Content-Type": "application/json"}

    if "openai" in upstream_url:
        headers["Authorization"] = f"Bearer {api_key}"
    elif "anthropic" in upstream_url:
        headers["x-api-key"] = api_key
        # Forward all anthropic-* headers from the client (version, beta features, etc.)
        for key, value in request.headers.items():
            if key.lower().startswith("anthropic-"):
                headers[key.lower()] = value
        # Ensure anthropic-version is always present
        if "anthropic-version" not in headers:
            headers["anthropic-version"] = "2023-06-01"

    return headers


def _parse_anthropic_sse_usage(events_data: list[dict[str, Any]]) -> dict[str, int]:
    """Extract usage from Anthropic SSE events."""
    input_tokens = 0
    output_tokens = 0
    for event in events_data:
        if event.get("type") == "message_start":
            msg = event.get("message", {})
            usage = msg.get("usage", {})
            input_tokens += usage.get("input_tokens", 0)
        elif event.get("type") == "message_delta":
            usage = event.get("usage", {})
            output_tokens += usage.get("output_tokens", 0)
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


def _parse_openai_sse_usage(events_data: list[dict[str, Any]]) -> dict[str, int]:
    """Extract usage from OpenAI SSE events."""
    input_tokens = 0
    output_tokens = 0
    for event in events_data:
        usage = event.get("usage")
        if usage:
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


def _mock_anthropic_sse_body() -> str:
    """Generate mock Anthropic SSE events for testing."""
    events = [
        {
            "type": "message_start",
            "message": {
                "id": "mock-msg-001",
                "type": "message",
                "role": "assistant",
                "usage": {"input_tokens": 15, "output_tokens": 0},
            },
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Sovereign reply."},
        },
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 25},
        },
    ]
    lines = []
    for event in events:
        lines.append(f"event: {event['type']}")
        lines.append(f"data: {json.dumps(event)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _mock_openai_sse_body() -> str:
    """Generate mock OpenAI SSE events for testing."""
    events = [
        {
            "id": "mock-chatcmpl-001",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"content": "Sovereign "}}],
        },
        {
            "id": "mock-chatcmpl-001",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"content": "reply."}}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 25},
        },
    ]
    lines = []
    for event in events:
        lines.append(f"data: {json.dumps(event)}")
        lines.append("")
    lines.append("data: [DONE]")
    lines.append("")
    return "\n".join(lines) + "\n"


async def _handle_mock_streaming(
    agent_pubkey: str,
    model: str,
    upstream_url: str,
) -> Response:
    """Return mock SSE events for testing streaming."""
    is_anthropic = "anthropic" in upstream_url
    if is_anthropic:
        sse_body = _mock_anthropic_sse_body()
        usage = {"input_tokens": 15, "output_tokens": 25}
    else:
        sse_body = _mock_openai_sse_body()
        usage = {"input_tokens": 15, "output_tokens": 25}

    cost_usdc = _calculate_cost_usdc(usage, model)
    debited_mint = _debit_agent(agent_pubkey, cost_usdc, json.dumps(usage))
    if not debited_mint:
        return Response(
            content=json.dumps({"error": "Insufficient Deposit Balance"}),
            status_code=402,
            headers={"Content-Type": "application/json"},
        )
    logger.info("Streaming charged %d USDC-equiv from %s", cost_usdc, debited_mint[:8])
    return Response(
        content=sse_body,
        status_code=200,
        media_type="text/event-stream",
    )


async def _handle_streaming(  # pragma: no cover
    agent_pubkey: str,
    body: dict[str, Any],
    model: str,
    upstream_url: str,
    headers: dict[str, str],
) -> StreamingResponse:
    """Stream SSE from upstream, parse usage, debit after completion."""
    is_anthropic = "anthropic" in upstream_url
    collected_events: list[dict[str, Any]] = []

    # Prevent upstream from compressing the SSE stream — avoids zlib
    # decompression issues when relaying chunked+gzip responses.
    headers["Accept-Encoding"] = "identity"

    async def event_generator() -> AsyncGenerator[bytes]:
        async with (
            httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT) as client,
            client.stream("POST", upstream_url, json=body, headers=headers) as resp,
        ):
            async for raw_bytes in resp.aiter_raw():
                # Relay raw bytes directly — no re-encoding issues
                yield raw_bytes

                # Parse SSE events from the raw bytes for usage tracking
                for line in raw_bytes.decode(errors="replace").splitlines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() != "[DONE]":
                            with contextlib.suppress(json.JSONDecodeError):
                                collected_events.append(json.loads(data_str))

        # After stream completes, parse usage and debit
        if is_anthropic:
            usage = _parse_anthropic_sse_usage(collected_events)
        else:
            usage = _parse_openai_sse_usage(collected_events)
        cost_usdc = _calculate_cost_usdc(usage, model)
        debited_mint = _debit_agent(agent_pubkey, cost_usdc, json.dumps(usage))
        if debited_mint:
            logger.info("Streaming charged %d USDC-equiv from %s", cost_usdc, debited_mint[:8])

    return StreamingResponse(
        content=event_generator(),
        media_type="text/event-stream",
    )


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
    is_streaming = body.get("stream", False)

    # --- Mock path ---
    if is_mock:
        if is_streaming:
            return await _handle_mock_streaming(agent_pubkey, model, upstream_url)

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

    # --- Real upstream path (requires API key) ---
    if not api_key:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail="Upstream API key not configured. Check your .env file.",
        )

    headers = _build_upstream_headers(upstream_url, api_key, request)

    if is_streaming:  # pragma: no cover
        return await _handle_streaming(agent_pubkey, body, model, upstream_url, headers)

    # --- Synchronous (non-streaming) real upstream path ---
    async with httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT) as client:  # pragma: no cover
        try:
            upstream_response = await client.post(
                upstream_url,
                json=body,
                headers=headers,
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

    uvicorn.run(app, host="0.0.0.0", port=18515)  # noqa: S104


if __name__ == "__main__":
    main()
