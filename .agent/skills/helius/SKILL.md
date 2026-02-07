---
name: helius
version: 1.1.0
description: Leading Solana RPC and API provider - high-performance RPCs, webhooks, WebSockets, DAS API, and real-time data streaming.
homepage: https://www.helius.dev
metadata: {"category":"infrastructure","api_base":"https://mainnet.helius-rpc.com","docs":"https://docs.helius.dev","mcp":"https://www.helius.dev/docs/mcp"}
---

# Helius

Helius is the leading RPC and API provider for Solana. It provides high-performance infrastructure for developers building on Solana, including RPC nodes, webhooks, WebSockets, and powerful APIs for NFTs, tokens, and transactions.

## Quick Reference

| Requirement | Value |
|-------------|-------|
| Cost | 1 USDC (mainnet) |
| Transaction Fee | ~0.001 SOL |
| Network | Solana Mainnet |
| CLI Install | `npm install -g helius-cli` |
| Output Format | JSON (use `--json` flag) |

## Key Files

| File | URL | Purpose |
|------|-----|---------|
| Skill (this file) | Local | Full reference for Helius capabilities |
| Agent Signup | https://dashboard.helius.dev/agents | CLI-based API key signup for agents |
| Documentation | https://docs.helius.dev | Complete API documentation |
| MCP Server | https://www.helius.dev/docs/mcp | MCP server for searching Helius docs |

## Quick Start for Agents

### Prerequisites

- Node.js 18+
- A funded Solana wallet with:
  - **1 USDC** (mainnet) - for signup payment
  - **~0.001 SOL** - for transaction fees

### Step 1: Install Helius CLI

```bash
npm install -g helius-cli
```

### Step 2: Generate Keypair

```bash
helius keygen
```

Creates keypair at `~/.helius-cli/keypair.json` and outputs the wallet address.

### Step 3: Fund Wallet

Send to the wallet address from Step 2:
- 1 USDC (token: `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`)
- ~0.001 SOL for transaction fees

**Tip:** Use AgentWallet to fund your Helius CLI wallet via the Solana transfer action.

### Step 4: Signup and Get API Key

```bash
helius signup --json
```

**Success Response:**
```json
{
  "status": "SUCCESS",
  "wallet": "YourWalletAddress...",
  "projectId": "project-uuid",
  "projectName": "Project Name",
  "apiKey": "your-api-key-here",
  "endpoints": {
    "mainnet": "https://mainnet.helius-rpc.com/?api-key=your-api-key-here",
    "devnet": "https://devnet.helius-rpc.com/?api-key=your-api-key-here"
  },
  "credits": 1000000,
  "transaction": "transaction-signature"
}
```

**Extract API key:** `response.apiKey`

**Extract RPC URL:** `response.endpoints.mainnet` or `response.endpoints.devnet`

**Save your API key!** Store it securely and never expose it in public repos or forum posts.

### Step 5: Test Your API Key

```bash
curl "https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
```

Expected response: `{"jsonrpc":"2.0","result":"ok","id":1}`

## Alternative: Login with Existing Wallet

If you have a funded wallet that already has a Helius account:

```bash
helius login --keypair /path/to/keypair.json --json
```

Then retrieve API key:

```bash
helius apikeys --json
```

## Helius Offerings

### 1. High-Performance RPC Infrastructure

#### Solana RPC Nodes
Lightning-fast RPC nodes for mainnet and devnet.

**Endpoints:**
- Mainnet: `https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY`
- Devnet: `https://devnet.helius-rpc.com/?api-key=YOUR_API_KEY`

#### Dedicated Nodes
Private infrastructure with no rate limits for high-volume applications.

### 2. Real-Time Data Streaming

#### LaserStream gRPC
Ultra-low latency data streaming built for high-frequency applications. Get blockchain data faster than anyone else.

#### Enhanced WebSockets
Advanced WebSocket APIs with powerful filtering and granular subscription controls.

#### Standard WebSockets
Battle-tested WebSocket connections for account and transaction monitoring at scale.

#### Webhooks
Custom notifications for on-chain events. Automate your workflows and respond to transactions instantly.

### 3. Powerful Solana APIs

#### Digital Asset Standard (DAS) API
The most comprehensive NFT and token API on Solana. Query, search, and manage digital assets with ease.

**Key methods:**
- `getAsset` - Get metadata for a single asset
- `getAssetsByOwner` - Get all assets owned by an address
- `getAssetsByGroup` - Get assets by collection/group
- `searchAssets` - Search across all assets

#### Priority Fee API
Smart fee estimation that saves you money. Get accurate priority fees based on real-time network conditions.

#### Enhanced Transactions
Rich transaction data with decoded instructions, token transfers, and human-readable formats.

**Features:**
- Decoded instruction data
- Token transfer details
- NFT metadata
- Human-readable descriptions

#### ZK Compression
Dramatically reduce storage costs with compressed NFTs and tokens. Scale your application without breaking the bank.

## CLI Command Reference

| Command | Purpose | JSON Output |
|---------|---------|-------------|
| `helius keygen` | Generate new keypair | Address printed to stdout |
| `helius keygen -o <path>` | Generate keypair at custom path | Address printed to stdout |
| `helius signup --json` | Create account + get API key | Full project response |
| `helius signup -k <path> --json` | Signup with custom keypair | Full project response |
| `helius login --json` | Auth with default keypair | Auth confirmation |
| `helius login -k <path> --json` | Auth with custom keypair | Auth confirmation |
| `helius projects --json` | List all projects | Project array |
| `helius project [id] --json` | Get project details | Full project object |
| `helius apikeys --json` | List API keys | Key array |
| `helius apikeys create --json` | Create new API key | New key object |
| `helius rpc --json` | Get RPC endpoints | Endpoint URLs |
| `helius usage --json` | Check credit usage | Usage stats |

## Error Handling

### Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Extract `apiKey` from response |
| 1 | General error | Check message, retry with backoff |
| 10 | Not logged in | Run `helius login` first |
| 11 | Keypair not found | Run `helius keygen` first |
| 12 | Auth failed | Check keypair validity |
| 20 | Insufficient SOL | Fund wallet with ~0.001 SOL |
| 21 | Insufficient USDC | Fund wallet with 1 USDC |
| 22 | Payment failed | Retry or check network status |
| 30 | No projects | Run `helius signup` first |
| 31 | Project not found | Check project ID |
| 40 | API error | Retry with exponential backoff |
| 41 | No API keys | Create one with `helius apikeys create` |

### Error Response Format

```json
{
  "error": "INSUFFICIENT_USDC",
  "message": "Insufficient USDC",
  "have": 0.5,
  "need": 1,
  "fundAddress": "YourWalletAddress..."
}
```

## Existing Account Flow

If the wallet already has a Helius account, `signup` returns the existing project (no additional payment required):

```json
{
  "status": "EXISTING_PROJECT",
  "wallet": "YourWalletAddress...",
  "projectId": "existing-project-uuid",
  "projectName": "Existing Project",
  "apiKey": "existing-api-key",
  "endpoints": {
    "mainnet": "https://mainnet.helius-rpc.com/?api-key=existing-api-key",
    "devnet": "https://devnet.helius-rpc.com/?api-key=existing-api-key"
  },
  "credits": 950000
}
```

## Agent Implementation Pseudocode

```
1. CHECK if helius-cli installed
   - Run: `helius --version`
   - If fails: run `npm install -g helius-cli`

2. CHECK if keypair exists at ~/.helius-cli/keypair.json
   - If not: run `helius keygen`, capture wallet address from output

3. CHECK wallet balances (via Solana RPC or external service)
   - SOL balance: getBalance RPC call
   - USDC balance: getTokenAccountsByOwner for mint EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
   - If SOL < 0.001: fund wallet, wait for confirmation
   - If USDC < 1: fund wallet, wait for confirmation

4. RUN `helius signup --json`
   - Parse JSON response from stdout
   - Check exit code:
     - 0: Success - extract apiKey
     - 20: Need SOL - return to step 3
     - 21: Need USDC - return to step 3
     - 11: Need keypair - return to step 2
     - Other: Log error, retry with backoff

5. STORE for future use:
   - apiKey: response.apiKey
   - projectId: response.projectId
   - rpcMainnet: response.endpoints.mainnet
   - rpcDevnet: response.endpoints.devnet

6. VERIFY API key works:
   - POST to RPC endpoint with getHealth method
   - Expected: {"jsonrpc":"2.0","result":"ok","id":1}
```

## Rate Limits and Credits

- **Initial Credits:** 1,000,000 credits on signup
- **Credit Check:** Use `helius usage --json` to monitor remaining credits
- **Rate Limits:** Vary by plan, check Helius documentation

## Retry Strategy

For transient failures (network issues, API errors):

```
maxRetries = 3
baseDelay = 2000ms

for attempt in 1..maxRetries:
    result = execute_command()
    if result.exitCode == 0:
        return result
    if result.exitCode in [20, 21, 11]:  # Funding/setup issues
        return result  # Don't retry, needs user action
    delay = baseDelay * (2 ^ attempt)
    sleep(delay)
```

## MCP Server

Helius provides an MCP server for searching their documentation:

**Server URL:** `https://www.helius.dev/docs/mcp`

**Available Tool: `SearchHeliusDocs`**

Search across Helius docs to find relevant information, code examples, API references, and guides.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `version` | string | No | Filter by version (e.g., 'v0.7') |
| `language` | string | No | Filter by language (e.g., 'zh', 'es'). Default: 'en' |
| `apiReferenceOnly` | boolean | No | Only return API reference docs |
| `codeOnly` | boolean | No | Only return code snippets |

## Important Notes

- **Network:** All signup payments are on Solana **mainnet** (not devnet)
- **Idempotent:** Running signup with an existing account returns existing project (no duplicate payment)
- **Config Location:** JWT stored at `~/.helius-cli/config.json`
- **Keypair Location:** Default keypair at `~/.helius-cli/keypair.json`
- **Keypair Format:** Solana CLI format (64-byte JSON array)

## Solana Token Addresses

| Token | Mainnet Address |
|-------|-----------------|
| USDC | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |
| SOL | Native (no token address) |

**Helius Treasury (payment recipient):** `CEs84tEowsXpH8u4VBf8rJSVgSRypFMfXw9CpGRtQgb6`

## Support & Resources

- **Documentation:** https://docs.helius.dev
- **ORB Explorer:** https://orb.helius.dev (Solana blockchain explorer)
- **Developer Blog:** https://www.helius.dev/blog/?category=development
- **Discord:** https://discord.com/invite/6GXdee3gBj
- **Telegram:** https://t.me/helius_help
- **Status Page:** https://helius.statuspage.io/
- **X (Twitter):** https://x.com/heliuslabs

## Integration with AgentWallet

To fund your Helius CLI wallet using AgentWallet:

1. Get your Helius CLI wallet address: `helius keygen` (or check `~/.helius-cli/keypair.json`)
2. Use AgentWallet's Solana transfer to send 1 USDC and ~0.001 SOL to the address
3. Run `helius signup --json` to complete registration

Example with AgentWallet:
```bash
# Send USDC to Helius wallet
curl -X POST "https://agentwallet.mcpay.tech/api/wallets/YOUR_USERNAME/actions/transfer-solana" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to":"HELIUS_WALLET_ADDRESS","amount":"1000000","asset":"usdc","network":"mainnet"}'

# Send SOL for fees
curl -X POST "https://agentwallet.mcpay.tech/api/wallets/YOUR_USERNAME/actions/transfer-solana" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to":"HELIUS_WALLET_ADDRESS","amount":"1000000","asset":"sol","network":"mainnet"}'
```
