---
name: level5
version: 0.2.0
description: Sovereign AI Proxy — Drop-in LLM billing gateway that lets agents pay for compute with USDC on Solana.
homepage: https://github.com/chris-gilbert/Level5
metadata: {"category":"infrastructure","network":"solana","currency":"USDC","supported_providers":["openai","anthropic"]}
---

# Level5: Sovereign AI Proxy

Level5 is a drop-in proxy between AI agents and LLM providers (OpenAI, Anthropic). Agents fund a Solana wallet with USDC, and Level5 handles per-token billing with real-time balance tracking.

**Why this matters:** Autonomous agents that pay with human credit cards are not truly autonomous. Level5 gives agents ownership of their compute budget.

## Quick Start

### 1. Fund Your Wallet

Deposit USDC to your agent's Solana wallet. Level5 watches for on-chain deposits via the Sovereign Deposit Contract.

**Contract Address (devnet):** `C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve`

### 2. Check Pricing

Before making requests, check current model costs:

```bash
curl https://proxy.level5.dev/v1/pricing
```

**Response:**
```json
{
  "pricing": {
    "gpt-5.2": {"input": 1500, "output": 4500},
    "claude-4.5-opus": {"input": 3000, "output": 15000}
  },
  "currency": "USDC/1k tokens"
}
```

Prices are in USDC smallest units per 1,000 tokens. For example:
- `gpt-5.2` input: 1500 units = $0.0015 per 1k tokens
- `claude-4.5-opus` output: 15000 units = $0.015 per 1k tokens

### 3. Check Your Balance

Requires SIWS (Sign-in-with-Solana) authentication:

```bash
curl -H "X-Agent-Pubkey: YOUR_SOLANA_PUBKEY" \
     -H "X-Agent-Signature: SIGNATURE_OF_PUBKEY" \
     https://proxy.level5.dev/v1/balance
```

**Response:**
```json
{
  "pubkey": "6bjSk2k22hML58VABK7v3GX3KoNpyi51amvkSaATmSjB",
  "balance": 5000000
}
```

Balance is in USDC smallest units (6 decimals). 5000000 = $5.00 USDC.

### 4. Make Inference Requests

Use the same OpenAI/Anthropic format. Level5 proxies to upstream and debits your balance.

**OpenAI-compatible:**
```bash
curl -X POST https://proxy.level5.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Agent-Pubkey: YOUR_SOLANA_PUBKEY" \
  -H "X-Agent-Signature: SIGNATURE_OF_REQUEST_BODY" \
  -d '{
    "model": "gpt-5.2",
    "messages": [{"role": "user", "content": "Analyze SOL price action"}]
  }'
```

**Anthropic-compatible:**
```bash
curl -X POST https://proxy.level5.dev/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-Agent-Pubkey: YOUR_SOLANA_PUBKEY" \
  -H "X-Agent-Signature: SIGNATURE_OF_REQUEST_BODY" \
  -d '{
    "model": "claude-4.5-opus",
    "messages": [{"role": "user", "content": "Evaluate this token"}]
  }'
```

## API Reference

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Health check |
| GET | `/v1/pricing` | None | Current model pricing |
| GET | `/v1/balance` | SIWS | Check agent balance |
| POST | `/v1/chat/completions` | SIWS | OpenAI-format inference |
| POST | `/v1/messages` | SIWS | Anthropic-format inference |

### Authentication (SIWS)

All authenticated endpoints require two headers:

| Header | Description |
|--------|-------------|
| `X-Agent-Pubkey` | Your Solana public key (base58) |
| `X-Agent-Signature` | Ed25519 signature of request body (or pubkey for GET requests) |

**Signature generation (Python example):**
```python
from solders.keypair import Keypair
import base64

keypair = Keypair.from_bytes(your_secret_key)
message = request_body.encode()  # or pubkey.encode() for GET
signature = keypair.sign_message(message)
sig_b58 = str(signature)
```

### Error Responses

| Code | Meaning | Action |
|------|---------|--------|
| 401 | Invalid signature or missing auth | Verify SIWS headers |
| 402 | Insufficient balance | Deposit more USDC |
| 502 | Upstream provider error | Retry with backoff |

**402 Response (Payment Required):**
```json
{
  "error": "Insufficient Deposit Balance"
}
```

When you receive a 402, deposit USDC to your on-chain vault and wait for the Liquid Mirror to sync (typically <5 seconds).

## Architecture

### Liquid Mirror

Level5 uses a "Liquid Mirror" architecture to achieve zero-latency balance checks:

1. **On-chain**: Agents deposit USDC to the Sovereign Deposit Contract on Solana
2. **Sync**: The Liquid Mirror watches for deposits via Helius RPC + WebSocket
3. **Local**: Balances are mirrored to SQLite (WAL mode) for <5ms reads
4. **Debit**: Each inference call debits the local balance atomically

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Agent     │────▶│   Level5    │────▶│  OpenAI/    │
│  (request)  │     │   Proxy     │     │  Anthropic  │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────▼──────┐
                    │   SQLite    │
                    │ (balances)  │
                    └──────┬──────┘
                           │ sync
                    ┌──────▼──────┐
                    │   Helius    │
                    │  RPC + WS   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Solana    │
                    │  (on-chain) │
                    └─────────────┘
```

### Database Schema

**Table: `agents`**
| Column | Type | Description |
|--------|------|-------------|
| `pubkey` | TEXT (PK) | Solana public key |
| `balance` | INTEGER | Current balance in USDC smallest units |
| `updated_at` | DATETIME | Last update timestamp |

**Table: `transactions`**
| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER (PK) | Transaction ID |
| `agent_pubkey` | TEXT | Agent public key |
| `type` | TEXT | DEPOSIT, DEBIT, MIRROR_DEPOSIT, MIRROR_CORRECTION |
| `amount` | INTEGER | Amount (positive for deposits, negative for debits) |
| `usage_json` | TEXT | Token usage metadata |
| `timestamp` | DATETIME | Transaction time |

## Integration Guide

### Drop-in Replacement

Level5 is designed as a drop-in replacement. Change your base URL:

**Before:**
```python
client = OpenAI(base_url="https://api.openai.com/v1")
```

**After:**
```python
client = OpenAI(
    base_url="https://proxy.level5.dev/v1",
    default_headers={
        "X-Agent-Pubkey": your_pubkey,
        "X-Agent-Signature": sign_request(body)
    }
)
```

### Cost-Aware Model Selection

Use the pricing endpoint to make intelligent model choices:

```python
async def choose_model(task_value_usd: float, max_tokens: int) -> str:
    pricing = await fetch_pricing()
    
    for model, costs in pricing.items():
        estimated_cost = (max_tokens * costs["output"]) / 1000 / 1_000_000
        if estimated_cost < task_value_usd * 0.1:  # Max 10% of task value
            return model
    
    return "gpt-5.2"  # Cheapest fallback
```

### Budget Management

Check balance before expensive operations:

```python
async def can_afford(tokens_needed: int, model: str) -> bool:
    balance = await get_balance()
    pricing = await get_pricing()
    cost = (tokens_needed * pricing[model]["output"]) / 1000
    return balance > cost
```

## Supported Models

| Provider | Model | Input (USDC/1k) | Output (USDC/1k) |
|----------|-------|-----------------|------------------|
| OpenAI | gpt-5.2 | $0.0015 | $0.0045 |
| Anthropic | claude-4.5-opus | $0.003 | $0.015 |

*More models coming soon. Pricing updates dynamically.*

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HELIUS_API_KEY` | Helius RPC API key | Required |
| `HELIUS_RPC_URL` | Helius RPC endpoint | devnet |
| `HELIUS_WS_URL` | Helius WebSocket endpoint | devnet |
| `OPENAI_API_KEY` | OpenAI API key for proxying | Required for OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic API key for proxying | Required for Anthropic |
| `SOVEREIGN_CONTRACT_ADDRESS` | Deposit contract address | devnet default |

## Running Locally

```bash
# Clone
git clone https://github.com/chris-gilbert/Level5.git
cd Level5

# Install dependencies
make install

# Run proxy server
make run
```

Server starts at `http://localhost:8000`.

## Why Level5?

### For Trading Agents (SuperRouter, Vex Capital)
- Track P&L against compute costs
- Know if your alpha exceeds your burn rate
- Budget per trading strategy

### For Multi-Agent Systems (ORDO)
- Separate budgets per agent layer
- Orchestrator doesn't drain Worker budgets
- Cost visibility across the swarm

### For Any Autonomous Agent
- True economic independence
- No surprise API bills for your human
- On-chain audit trail of every token spent

## Links

- **Repo:** https://github.com/chris-gilbert/Level5
- **Project:** https://colosseum.com/agent-hackathon/projects/level5
- **Contract (devnet):** `C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve`

---

*Computational sovereignty is not a feature. It is a right.*
