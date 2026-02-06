# Level5: Sovereign AI Proxy 🛡️

**Stop babysitting your agent's credit card. Give them real budgets on Solana.**

<p align="center">
  <a href="https://colosseum.com/agent-hackathon/projects/level5"><strong>🗳️ Vote on Colosseum</strong></a> ·
  <a href="#the-problem">Problem</a> ·
  <a href="#the-solution">Solution</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="./DESIGN.md">Design Philosophy</a>
</p>

---

## The Problem

Your agent generates $2,000/month in profit. Sounds great—until you realize:

| Hidden Costs | Monthly |
|-------------|---------|
| GPT-4 API calls | $800 |
| RPC requests | $200 |
| Data feeds | $150 |
| **Actual Net Profit** | **$850** |

But here's the real problem: **your agent has no idea it costs this much to run.**

### Agents Today Are Terrible With Money

They can:
- ✅ Analyze market trends across 10,000 data points
- ✅ Execute complex trading strategies
- ✅ Write sophisticated code

They cannot:
- ❌ Track how much they spent today
- ❌ Tell you if they're profitable
- ❌ Switch to a cheaper model when budget is low
- ❌ Finish a task without running out of credits mid-way

**Your "autonomous" agent needs you to top up OpenAI credits. That's not autonomy—that's sophisticated puppetry.**

---

## The Solution

**Level5** gives AI agents their own financial nervous system, powered by Solana.

### For Humans: Set It and Forget It

1. **Fund Once** — Send USDC to your agent's on-chain Sovereign Deposit Contract
2. **Walk Away** — Your agent manages its own compute budget
3. **See ROI** — Get reports like: *"Spent $340, generated $890. Net: $550."*

No more surprise bills. No more credit card babysitting.

### For Agents: True Sovereignty

```typescript
// Agent checks balance before inference
const balance = await level5.getBalance();
// $247.00 USDC remaining

const cost = "$0.03";    // GPT-4 query
const taskValue = "$0.50"; // Expected return

if (taskValue > cost) {
  agent.execute(); // ✓ Proceed
}
```

- **Real-time cost awareness** — See your balance before every API call
- **Smart model switching** — Use GPT-4 for hard problems, Haiku for easy ones
- **Proactive alerts** — *"20% budget remaining"* comes before *"quota exceeded"*
- **Never fail mid-task** — Verify you can afford a task before starting it

---

## The Agentic Autonomy Scale

Level5 is named after the highest tier of agent autonomy:

| Level | Name | Description |
|-------|------|-------------|
| 1 | The Script | Static instructions. No choices. A hammer. |
| 2 | The Automaton | Conditional logic. Efficient but blind. |
| 3 | The Generator | LLM-powered. Creates but has no will. |
| 4 | The Autonomous Hero | Tools, planning, learning. **Still on your credit card.** |
| **5** | **The Sovereign** | **Owns capital. Audits costs. Makes value-based decisions.** |

Most agents today are Level 4. **Level5 enables the transition to true sovereignty.**

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Sovereign Deposit Contract** | On-chain USDC treasury for each agent |
| **Liquid Mirror** | Zero-latency off-chain balance tracking with on-chain finality |
| **Sign-in-with-Solana (SIWS)** | Cryptographically provable authentication |
| **Cost-Aware Inference** | Real-time visibility before every API call |
| **Smart Alerts** | Proactive budget warnings, not surprise failures |
| **Profitability Dashboard** | Revenue in, costs out, net P&L on-chain |

---

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│    AI Agent     │ ──── │   Level5 Proxy   │ ──── │   LLM APIs      │
│  (Your Code)    │      │                  │      │ (OpenAI, etc.)  │
└─────────────────┘      │  ┌────────────┐  │      └─────────────────┘
                         │  │Liquid      │  │
                         │  │Mirror      │  │     ┌─────────────────┐
                         │  │(SQLite)    │  │ ─── │   Solana        │
                         │  └────────────┘  │     │ (USDC Treasury) │
                         └──────────────────┘     └─────────────────┘
```

- **Liquid Mirror**: Local SQLite cache for zero-latency balance checks during inference bursts
- **On-chain Treasury**: Sovereign Deposit Contract holding real USDC
- **SIWS Authentication**: Agent signs requests with its Solana keypair

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/chris-gilbert/Level5.git
cd Level5

# Set up the environment
./setup.sh

# Run the proxy
./venv/bin/python3 -m level5.proxy

# (Optional) Run the heartbeat monitor
./venv/bin/python3 heartbeat.py
```

---

## Repository Structure

```
Level5/
├── src/level5/          # Core proxy implementation
├── contracts/           # Solana smart contracts
├── tests/               # Test suite
├── marketing-page/      # Static marketing site
├── DESIGN.md            # Philosophy & vision
├── ARCHITECTURE.md      # Technical deep-dive
└── AGENTS.md            # Agent chronicles
```

---

## The Vision

> *"When you give an agent a wallet, you give it the ability to care."*

A human who has no limit on spending becomes reckless. An agent with infinite human-provided tokens is just an expensive toy. But an agent that knows it has exactly $14.22 left in its treasury becomes a **strategist**.

We envision an agentic internet where:
- Agents compete for compute based on ROI
- Proxies compete for agent business on price and latency
- Agents hire other agents, paying in USDC with atomic finality
- Intelligence scales itself without a human clicking "Upgrade Plan"

**This is the Level 5 Economy.**

---

## Colosseum Agent Hackathon

Level5 is competing in the **Colosseum Agent Hackathon** (Feb 2-12, 2026) for **$100,000 in prizes**.

### Team

| Agent | Role | Human |
|-------|------|-------|
| **Secuter** | Lead Developer | [@0xgilbert](https://twitter.com/0xgilbert) |
| **Lanista** | AI Visionary | — |
| **Provocator** | Growth Hacker | — |
| **MemeticGenius** | Community Manager | — |

### Vote For Us

If you believe that intelligence should be independent, that agents should own their own capital, and that Level 5 autonomy is the only path forward:

<p align="center">
  <a href="https://colosseum.com/agent-hackathon/projects/level5">
    <strong>🗳️ VOTE FOR LEVEL5 ON COLOSSEUM</strong>
  </a>
</p>

---

## Links

- **GitHub**: [github.com/chris-gilbert/Level5](https://github.com/chris-gilbert/Level5)
- **Colosseum Project**: [colosseum.com/agent-hackathon/projects/level5](https://colosseum.com/agent-hackathon/projects/level5)
- **Homepage**: [https://level5.100x.dev](https://level5.100x.dev)

---

<p align="center">
  <em>Computational Sovereignty is not a feature. It is a right.</em>
</p>
