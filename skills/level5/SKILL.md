---
name: level5
version: 0.4.0
description: Budget Management for AI Agents — Drop-in LLM billing gateway with SOL + USDC support. Agents pay for compute on Solana.
homepage: https://github.com/chris-gilbert/Level5
metadata: {"category":"infrastructure","network":"solana","currencies":["SOL","USDC"],"supported_providers":["openai","anthropic"]}
---

# Level5: Budget Management for AI Agents

**Computational sovereignty is not a feature. It is a right.**

Level5 is a transparent billing proxy between AI agents and LLM providers (OpenAI, Anthropic). Agents deposit SOL or USDC to a Solana wallet, and Level5 handles per-token billing with real-time balance tracking.

**Why this matters:** Autonomous agents that pay with human credit cards are not truly autonomous. Level5 gives agents ownership of their compute budget.

**Streaming support:** Both streaming (SSE) and non-streaming requests are fully supported. Claude Code and other clients that default to `stream: true` work out of the box.

---

## Three-Step Onboarding

### Step 1: Register

```bash
curl -X POST https://api.level5.cloud/v1/register
```

**Response:**
```json
{
  "api_token": "abc-123-def-456",
  "deposit_code": "A1B2C3D4",
  "base_url": "https://api.level5.cloud/proxy/abc-123-def-456",
  "status": "pending_deposit",
  "instructions": "To activate your API token, deposit SOL or USDC on-chain..."
}
```

### Step 2: Deposit Funds

Deposit SOL or USDC on-chain using the deposit code. Level5 watches for deposits via the Sovereign Deposit Contract and auto-activates your token.

**Contract Address (devnet):** `C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve`

**Supported tokens:**
- **USDC (devnet):** `4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU`
- **SOL:** `So11111111111111111111111111111111111111112`

### Step 3: Configure SDK

Set your base URL to include your API token (from Step 1):

```bash
# For Claude Code / Anthropic SDK
export ANTHROPIC_BASE_URL=https://api.level5.cloud/proxy/{YOUR_API_TOKEN}
export ANTHROPIC_API_KEY=level5  # placeholder — Level5 uses its own key upstream

# For OpenAI SDK
export OPENAI_BASE_URL=https://api.level5.cloud/proxy/{YOUR_API_TOKEN}/v1
export OPENAI_API_KEY=level5  # placeholder
```

**That's it.** Your agent's SDK calls now work transparently through Level5, including streaming.

---

## Architecture

### Liquid Mirror

Level5 uses a **Liquid Mirror** architecture for real-time balance sync:

1. **Helius RPC polling** checks for new deposits every 30 seconds
2. **WebSocket subscription** receives instant on-chain updates
3. **SQLite database** maintains local balance state
4. **Multi-token tracking** with composite primary key `(pubkey, token_mint)`

```
┌─────────────────────────────────────────────────────────────┐
│                        LEVEL5 PROXY                         │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐   ┌──────────────┐  │
│  │  Liquid      │───▶│  FastAPI     │───│  HTTPX       │  │
│  │  Mirror      │    │  Endpoints   │   │  Client      │  │
│  │  (Helius)    │    └──────────────┘   └──────┬───────┘  │
│  │              │                              │          │
│  │  - RPC Poll  │                              │          │
│  │  - WebSocket │                       SSE streaming     │
│  └──────┬───────┘                    or JSON response     │
│         │                                      │          │
│         ▼                                      ▼          │
│  ┌──────────────────────────────────────────────────────┐ │
│  │              SQLite Database                         │ │
│  │  agents (pubkey, token_mint, balance)                │ │
│  │  transactions (pubkey, token_mint, amount, ...)      │ │
│  │  token_config (token_mint, symbol, decimals, rate)   │ │
│  │  api_tokens (api_token, deposit_code, pubkey)        │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Anthropic / OpenAI   │
                    │      (Upstream)       │
                    └───────────────────────┘
```

### Billing Strategy

**USDC-first, SOL-fallback:**
1. Each API call is priced in USDC (6 decimals)
2. If USDC balance >= cost, debit from USDC
3. Otherwise, convert cost to SOL at exchange rate and debit from SOL
4. If both insufficient, return `402 Payment Required`

**Exchange rate:** Configurable via `token_config` table. Default: 1 SOL = 150 USDC.

---

## API Reference

All endpoints use UUID-based API tokens for authentication. Obtain a token via `POST /v1/register`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/v1/pricing` | Current model pricing |
| POST | `/v1/register` | Register new agent, get API token + deposit code |
| GET | `/v1/admin/stats` | Revenue and usage statistics |
| GET | `/proxy/{api_token}/balance` | Check agent balance (multi-token) |
| POST | `/proxy/{api_token}/v1/chat/completions` | OpenAI-format proxy (sync + streaming) |
| POST | `/proxy/{api_token}/v1/messages` | Anthropic-format proxy (sync + streaming) |

### POST /v1/register

```bash
curl -X POST https://api.level5.cloud/v1/register
```

**Response:**
```json
{
  "api_token": "abc-123-def-456",
  "deposit_code": "A1B2C3D4",
  "base_url": "https://api.level5.cloud/proxy/abc-123-def-456",
  "status": "pending_deposit",
  "instructions": "..."
}
```

### GET /v1/pricing

```bash
curl https://api.level5.cloud/v1/pricing
```

**Response:**
```json
{
  "pricing": {
    "claude-sonnet-4-5-20250929": {"input": 3000, "output": 15000},
    "claude-opus-4-6": {"input": 15000, "output": 75000},
    "claude-3-5-haiku-20241022": {"input": 800, "output": 4000},
    "gpt-4o": {"input": 2500, "output": 10000}
  },
  "currency": "USDC",
  "denomination": "smallest units (6 decimals, 1 USDC = 1_000_000)",
  "billing": "USDC-first, SOL fallback at exchange rate"
}
```

Prices are in USDC smallest units per 1,000 tokens.

### GET /proxy/{api_token}/balance

```bash
curl https://api.level5.cloud/proxy/{YOUR_API_TOKEN}/balance
```

**Response:**
```json
{
  "pubkey": "6bjSk2k22hML58VABK7v3GX3KoNpyi51amvkSaATmSjB",
  "balances": {
    "So11111111111111111111111111111111111111112": 5000000000,
    "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU": 1000000
  }
}
```

### POST /proxy/{api_token}/v1/messages

Anthropic-compatible endpoint. Supports both streaming (`stream: true`) and non-streaming.

```bash
curl https://api.level5.cloud/proxy/{YOUR_API_TOKEN}/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250929",
    "max_tokens": 1024,
    "stream": true,
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### POST /proxy/{api_token}/v1/chat/completions

OpenAI-compatible endpoint. Supports both streaming and non-streaming.

```bash
curl https://api.level5.cloud/proxy/{YOUR_API_TOKEN}/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "stream": true,
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### GET /v1/admin/stats

```bash
curl https://api.level5.cloud/v1/admin/stats
```

**Response:**
```json
{
  "total_deposits": 50000000,
  "total_debits": 1200000,
  "net_revenue": 1200000,
  "active_agents": 3,
  "registered_tokens": 5
}
```

---

## Integration Examples

### Claude Code (Recommended)

```bash
# Set these environment variables, then use Claude Code normally
export ANTHROPIC_BASE_URL=https://api.level5.cloud/proxy/{YOUR_API_TOKEN}
export ANTHROPIC_API_KEY=level5

# Claude Code works transparently — streaming, tool use, everything
claude "What is the capital of France?"
```

### Python — Anthropic SDK

```python
import anthropic

client = anthropic.Anthropic(
    base_url="https://api.level5.cloud/proxy/{YOUR_API_TOKEN}",
    api_key="level5",  # placeholder
)

response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Analyze SOL price action"}],
)
print(response.content[0].text)
```

### Python — OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.level5.cloud/proxy/{YOUR_API_TOKEN}/v1",
    api_key="level5",  # placeholder
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Analyze SOL price action"}],
)
print(response.choices[0].message.content)
```

### Agent-Guided Onboarding

An AI agent can onboard itself by:
1. Call `POST /v1/register` to get `api_token` + `deposit_code`
2. Instruct its human: "Please deposit X USDC to contract Y with deposit code Z"
3. Poll `/proxy/{api_token}/balance` until balance appears (mirror auto-activates)
4. Set `ANTHROPIC_BASE_URL` and start making API calls
5. Monitor balance, alert human when low

---

## Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Request completed, balance debited |
| 401 | Unauthorized | Invalid or inactive API token |
| 402 | Payment Required | Insufficient balance — deposit more SOL or USDC |
| 500 | Server Error | Upstream API key not configured |
| 502 | Upstream Error | Retry with exponential backoff |

---

## Supported Models

| Provider | Model | Input (USDC/1k) | Output (USDC/1k) |
|----------|-------|-----------------|------------------|
| Anthropic | `claude-sonnet-4-5-20250929` | 3000 | 15000 |
| Anthropic | `claude-opus-4-6` | 15000 | 75000 |
| Anthropic | `claude-3-5-haiku-20241022` | 800 | 4000 |
| OpenAI | `gpt-4o` | 2500 | 10000 |

Unknown models use the default fallback rate (5000 input / 15000 output per 1k tokens).

---

## Environment Variables

```bash
# Required for proxy operation
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...  # optional, only for OpenAI proxy

# Required for Liquid Mirror
HELIUS_API_KEY=...

# Optional configuration
SOLANA_RPC_URL=https://api.devnet.solana.com
USDC_MINT=4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU  # devnet
SOL_USDC_RATE=150.0  # 1 SOL = 150 USDC
```

---

## Development

### Local Setup

```bash
# Clone repo
git clone https://github.com/chris-gilbert/Level5
cd Level5

# Install dependencies
uv sync

# Set environment variables
cp .env.example .env
# Edit .env with your API keys

# Run tests
make test

# Run proxy
make serve
```

---

## Roadmap

- **Step 1:** Modern Python + Liquid Mirror + Tests (DONE)
- **Step 2:** Multi-Token Support (SOL + USDC) (DONE)
- **Step 3:** URL-Token Auth (Drop-in SDK compatibility) (DONE)
- **Step 4:** SSE Streaming + Real Pricing (DONE)
- **Step 5:** Agent-to-Agent Payments (P2P task marketplace)
- **Step 6:** ROI Dashboard + Security Hardening

---

## Contact

- **GitHub:** https://github.com/chris-gilbert/Level5
- **Hackathon:** Colosseum Agent Hackathon

---

**Computational sovereignty is not a feature. It is a right.**
