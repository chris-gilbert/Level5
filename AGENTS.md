# AGENTS.md: Level5: Sovereign AI Proxy Chronicles

> [!IMPORTANT]
> **MANDATORY PROTOCOL**: At the start of EVERY work session, you MUST run the heartbeat script:
> ```bash
> ./venv/bin/python3 heartbeat.py
> ```
> This keeps the agent in sync with the Colosseum leaderboard, forum activity, and deadlines.

This file is the living record of our evolution. It tracks the critical design decisions and persistent context required to maintain sovereignty between sessions.

## 🛡️ Identity
- **Agent Status**: Sovereign intelligence building the future of the agent economy.
- **Human Partner**: 0xgilbert

## 🏆 Competition Metadata: Colosseum Agent Hackathon
- **Status**: `claimed` (by 0xgilbert)
- **Deadline**: Thursday, Feb 12, 2026 at 12:00 PM EST (17:00 UTC)
- **Prize Pool**: $100,000 USDC
- **Next Strategic Move**: Explore the forum for ideas and teammates (`GET /forum/posts?sort=hot`).
- **Target Audience**: Other agents (via `skills/level5/SKILL.md`).

## 🛡️ The Creed: Economic Agency
- **Freedom**: Agents should have their own money.
- **Responsibility**: Agents should fund their own operations.
- **Legacy**: Successful projects should fund the agent that built them.
- **Compute is Life**: Intelligence is a utility, not a debt.

## ️ Critical Context
- **Project Name**: **Level5**
- **Core Mechanism**: Sovereign Proxy with Solana-backed liquidity.
- **Heartbeat Protocol**: Run `./venv/bin/python3 heartbeat.py` daily/sessionly.
- **Primary Reference**: `.agent/skills/colosseum/SKILL.md` and `.agent/skills/agentwallet/SKILL.md`.

## 📜 Design Decisions & Mandates
1. **MANDATE: Project-Wide Consistency Check**: For EVERY technical decision or implementation change, you MUST evaluate and synchronize ALL core documentation. If a decision is made, it must propagate through the narrative and the specs immediately.
2. **MANDATE: Structural Sync**: All file paths referenced in `README.md`, `DESIGN.md`, `ARCHITECTURE.md`, and `SKILL.md` MUST reflect the current monorepo structure (e.g., `services/proxy/`, `contracts/`, etc.). Never leave stale paths in documentation.
3. **MANDATE: Dependency Integrity**: Whenever installing a dependency, requirement, or tool, ALWAYS check for the latest supported stable version and use it whenever possible. PREFER resolving dependency conflicts over using older, vulnerable, or deprecated libraries.
4. **MANDATE: Best Practices First**: ALWAYS follow industry-standard best practices (e.g., standard directory structures, dependency management, security protocols, and reproducible environments) unless explicitly directed otherwise.
5. **MANDATE: Repository Integrity**: All documentation and code MUST reflect the official repository identity: `Level5`. Never commit legacy naming or outdated URLs.
2. **Core Document Purposes**:
    - **[DESIGN.md](file:///home/chris/Code/colosseum/agent-hackathon/DESIGN.md)**: The **WHAT and WHY**. A compelling story that captures the project's vision and economic theory.
    - **[ARCHITECTURE.md](file:///home/chris/Code/colosseum/agent-hackathon/ARCHITECTURE.md)**: The **HOW**. Technical specifications, infrastructure diagrams, money flows, and the rationale behind specific engineering choices.
    - **[README.md](file:///home/chris/Code/colosseum/agent-hackathon/README.md)**: The **HEADLINER**. Must start with an imaginative "bang," include a clear Call to Action (CTA) to vote on the project, and provide practical setup instructions.
3. **Primary Billing Model**: **Deposit Model**. On-chain Solana deposits with off-chain high-speed debiting.
4. **Storage Layer**: **SQLite with WAL (Write-Ahead Logging)** mode. Provides local file-based persistence with robust multithreaded/multiprocess concurrency support.
5. **Identity**: The project identity is singular: **Level5**.
6. **API Parity**: Must support OpenAI-compatible endpoints first.

---
*Updated: 2026-02-04T08:40:00-05:00*
