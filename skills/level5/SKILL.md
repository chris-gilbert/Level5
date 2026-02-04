---
name: level5
description: A drop-in LLM proxy that enables agents to pay for compute per-token using Solana deposits.
---

# Sovereign Proxy Skill

This skill allows an AI agent to interface with a Sovereign Proxy to find pricing, check balances, and pay for compute.

## 🛠️ API Endpoints

### 1. Get Pricing
Returns the current cost per token for supported models.
```bash
curl https://proxy.example.com/v1/pricing
```
**Response:**
```json
{
  "pricing": {
    "claude-3-5-sonnet": { "input": 0.003, "output": 0.015, "currency": "USDC/1k" },
    "gpt-5.2": { "input": 0.0015, "output": 0.0045, "currency": "USDC/1k tokens" },
    "claude-4.5-opus": { "input": 0.003, "output": 0.015, "currency": "USDC/1k tokens" }
  }
}
```

### 2. Check Balance
If you have a deposit/session balance, check your remaining runway.
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" https://proxy.example.com/v1/balance
```

### 3. Request Inference
Standard OpenAI/Anthropic format. If no balance/signature is provided, expects an `HTTP 402` challenge.
```bash
curl -X POST https://proxy.example.com/v1/chat/completions ...
```

## 🛡️ Usage Strategy

1. **Check Pricing**: Before starting a long task, check if the current model fits your budget.
2. **Handle 402s**: Always be prepared to catch a 402 response and use your `AgentWallet` to sign the required payment.
3. **Switch Proxies**: If `latency` or `pricing` exceeds your threshold, search for alternative proxy endpoints and update your `base_url`.
