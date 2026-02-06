---
name: level5
version: 0.3.0
description: Sovereign AI Proxy — Drop-in LLM billing gateway with SOL + USDC support. Agents pay for compute on Solana.
homepage: https://github.com/chris-gilbert/Level5
metadata: {"category":"infrastructure","network":"solana","currencies":["SOL","USDC"],"supported_providers":["openai","anthropic"]}
---

# Level5: Sovereign AI Proxy

**Computational sovereignty is not a feature. It is a right.**

Level5 is a transparent billing proxy between AI agents and LLM providers (OpenAI, Anthropic). Agents deposit SOL or USDC to a Solana wallet, and Level5 handles per-token billing with real-time balance tracking.

**Why this matters:** Autonomous agents that pay with human credit cards are not truly autonomous. Level5 gives agents ownership of their compute budget.

---

## Two-Step Onboarding

### Step 1: Deposit Funds

Deposit SOL or USDC to your agent's Solana wallet. Level5 watches for on-chain deposits via the Sovereign Deposit Contract.

**Contract Address (devnet):** `C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve`

**Supported tokens:**
- **USDC (devnet):** `4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU`
- **SOL:** `So11111111111111111111111111111111111111112`

### Step 2: Configure SDK

Set your base URL to include your Solana pubkey:

```bash
# For Anthropic SDK
export ANTHROPIC_BASE_URL=https://api.level5.cloud/proxy/{YOUR_SOLANA_PUBKEY}
export ANTHROPIC_API_KEY=level5  # placeholder

# For OpenAI SDK
export OPENAI_BASE_URL=https://api.level5.cloud/proxy/{YOUR_SOLANA_PUBKEY}/v1
export OPENAI_API_KEY=level5  # placeholder
```

**That's it.** Your agent's SDK calls now work transparently through Level5.

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
│  │  - WebSocket │                              │          │
│  └──────┬───────┘                              │          │
│         │                                      │          │
│         ▼                                      ▼          │
│  ┌──────────────────────────────────────────────────────┐ │
│  │              SQLite Database                         │ │
│  │  agents (pubkey, token_mint, balance)                │ │
│  │  transactions (pubkey, token_mint, amount, ...)      │ │
│  │  token_config (token_mint, symbol, decimals, rate)   │ │
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

All endpoints support both SOL and USDC. No authentication required — the pubkey in the URL is the auth token.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/v1/pricing` | Current model pricing |
| GET | `/proxy/{pubkey}/balance` | Check agent balance (multi-token) |
| POST | `/proxy/{pubkey}/v1/chat/completions` | OpenAI-format proxy |
| POST | `/proxy/{pubkey}/v1/messages` | Anthropic-format proxy |

### GET /v1/pricing

```bash
curl https://api.level5.cloud/v1/pricing
```

**Response:**
```json
{
  "pricing": {
    "gpt-5.2": {"input": 1500, "output": 4500},
    "claude-4.5-opus": {"input": 3000, "output": 15000}
  },
  "currency": "USDC",
  "denomination": "smallest units (6 decimals, 1 USDC = 1_000_000)",
  "billing": "USDC-first, SOL fallback at exchange rate"
}
```

Prices are in USDC smallest units per 1,000 tokens. Example:
- `gpt-5.2` input: 1500 units = $0.0015 per 1k tokens
- `claude-4.5-opus` output: 15000 units = $0.015 per 1k tokens

### GET /proxy/{pubkey}/balance

```bash
curl https://api.level5.cloud/proxy/{YOUR_PUBKEY}/balance
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

Balances are in smallest units (lamports for SOL, microunits for USDC).

### POST /proxy/{pubkey}/v1/chat/completions

OpenAI-compatible endpoint. Replace `https://api.openai.com` with `https://api.level5.cloud/proxy/{YOUR_PUBKEY}`.

**Request:**
```bash
curl https://api.level5.cloud/proxy/{YOUR_PUBKEY}/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.2",
    "messages": [{"role": "user", "content": "Analyze SOL price action"}]
  }'
```

**Response:** Standard OpenAI response format with usage data.

### POST /proxy/{pubkey}/v1/messages

Anthropic-compatible endpoint. Replace `https://api.anthropic.com` with `https://api.level5.cloud/proxy/{YOUR_PUBKEY}`.

**Request:**
```bash
curl https://api.level5.cloud/proxy/{YOUR_PUBKEY}/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-4.5-opus",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Analyze SOL price action"}]
  }'
```

**Response:** Standard Anthropic response format with usage data.

---

## Integration Examples

### Python — Anthropic SDK

```python
import anthropic

client = anthropic.Anthropic(
    base_url="https://api.level5.cloud/proxy/{YOUR_PUBKEY}",
    api_key="level5",  # placeholder
)

response = client.messages.create(
    model="claude-4.5-opus",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Analyze SOL price action"}],
)
print(response.content[0].text)
```

### Python — OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.level5.cloud/proxy/{YOUR_PUBKEY}/v1",
    api_key="level5",  # placeholder
)

response = client.chat.completions.create(
    model="gpt-5.2",
    messages=[{"role": "user", "content": "Analyze SOL price action"}],
)
print(response.choices[0].message.content)
```

### Environment Variables (Zero Code Changes)

Set environment variables and your existing code works unchanged:

```bash
# For Anthropic SDK
export ANTHROPIC_BASE_URL=https://api.level5.cloud/proxy/{YOUR_PUBKEY}
export ANTHROPIC_API_KEY=level5

# For OpenAI SDK
export OPENAI_BASE_URL=https://api.level5.cloud/proxy/{YOUR_PUBKEY}/v1
export OPENAI_API_KEY=level5
```

---

## Database Schema

### agents table
```sql
CREATE TABLE agents (
    pubkey TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    balance INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (pubkey, token_mint)
);
```

### transactions table
```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pubkey TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    amount INTEGER NOT NULL,
    tx_type TEXT NOT NULL,
    usage_json TEXT,
    timestamp TEXT NOT NULL
);
```

### token_config table
```sql
CREATE TABLE token_config (
    token_mint TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    decimals INTEGER NOT NULL,
    usd_rate REAL NOT NULL
);
```

---

## Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Request completed, balance debited |
| 402 | Payment Required | Insufficient balance — deposit more SOL or USDC |
| 500 | Server Error | Contact Level5 support |
| 502 | Upstream Error | Retry with exponential backoff |

---

## Why Level5?

### For Trading Agents
- **Pay-per-call billing** — no monthly subscriptions or upfront commitments
- **Real-time balance tracking** — agents always know their compute budget
- **Sovereign wallets** — agents control their own funds

### For Multi-Agent Systems
- **Shared treasury** — multiple agents can draw from the same wallet
- **Transaction history** — full audit trail of all API usage
- **Cost attribution** — track spending per agent, per model, per task

### For Researchers
- **Transparent pricing** — no hidden fees or rate limits
- **Multi-provider support** — compare OpenAI and Anthropic without vendor lock-in
- **Open source** — audit the code, deploy your own instance

---

## Supported Models

| Provider | Model | Input (USDC/1k) | Output (USDC/1k) |
|----------|-------|-----------------|------------------|
| OpenAI | `gpt-5.2` | 1500 | 4500 |
| Anthropic | `claude-4.5-opus` | 3000 | 15000 |

Contact us to add more models or providers.

---

## Environment Variables

```bash
# Required for proxy operation
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=ant-...

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
uv run pytest tests/ -v --cov

# Run proxy
uv run uvicorn level5.proxy.main:app --reload
```

### Running Tests

```bash
# All tests with coverage
uv run pytest tests/ -v --cov --cov-fail-under=80

# Specific test file
uv run pytest tests/test_endpoints.py -v

# With verbose output
uv run pytest tests/ -vv -s
```

---

## Roadmap

- ✅ **Step 1:** Modern Python + Liquid Mirror + Tests (DONE)
- ✅ **Step 2:** Multi-Token Support (SOL + USDC) (DONE)
- ✅ **Step 3:** URL-Token Auth (Drop-in SDK compatibility) (DONE)
- **Step 4:** Arbitrage Engine (Buy SOL when cheap, sell when expensive)
- **Step 5:** Agent-to-Agent Payments (P2P task marketplace)
- **Step 6:** ROI Dashboard + Security Hardening

---

## Contact

- **GitHub:** https://github.com/chris-gilbert/Level5
- **Issues:** https://github.com/chris-gilbert/Level5/issues
- **Hackathon:** Colosseum Agent Hackathon ($100k USDC prize pool)

---

**Computational sovereignty is not a feature. It is a right.**
