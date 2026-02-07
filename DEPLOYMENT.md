# Level5 Deployment Guide

Three deployment environments are documented below: local development (localhost + local validator), staging (public server + Solana devnet), and production (public server + Solana mainnet-beta).

---

## Prerequisites

Install these on every machine that will build or run Level5:

| Tool | Version | Install |
|------|---------|---------|
| Python | >= 3.10 | System package manager or pyenv |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Rust + Cargo | stable | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Solana CLI | >= 1.18 | `sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"` |
| Anchor CLI | >= 0.30 | `cargo install --git https://github.com/coral-xyz/anchor avm && avm install latest && avm use latest` |
| Node.js | >= 18 | For Anchor tests only |

---

## 1. Local Development (localhost + local validator)

This environment runs everything on your machine with a local Solana test validator. No real funds, no external services. Ideal for rapid iteration.

### 1.1 Clone and install

```bash
git clone https://github.com/chris-gilbert/Level5
cd Level5
uv sync --all-groups
```

### 1.2 Start the local Solana validator

In a dedicated terminal:

```bash
solana-test-validator --reset
```

This gives you a local RPC at `http://localhost:8899` and a WebSocket at `ws://localhost:8900`.

### 1.3 Configure a local wallet

```bash
solana-keygen new --outfile ~/.config/solana/id.json --no-bip39-passphrase
solana config set --url localhost
solana airdrop 10   # fund the wallet with 10 SOL
```

### 1.4 Build and deploy the contract

```bash
cd contracts/sovereign-contract
anchor build
anchor deploy --provider.cluster localnet
cd ../..
```

Verify the program ID matches `C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve`. If Anchor generated a different key, update `declare_id!()` in `lib.rs`, `Anchor.toml`, and the `SOVEREIGN_CONTRACT_ADDRESS` env var, then rebuild and redeploy.

### 1.5 Create your `.env`

```bash
cp .env.example .env
```

Edit `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-XXXX          # your real Anthropic key
OPENAI_API_KEY=sk-XXXX                 # optional, only if proxying OpenAI

# Local validator — no Helius needed
HELIUS_API_KEY=unused
HELIUS_RPC_URL=http://localhost:8899
HELIUS_WS_URL=ws://localhost:8900

SOLANA_RPC_URL=http://localhost:8899
SOVEREIGN_CONTRACT_ADDRESS=C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve

USDC_MINT=4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU
SOL_USDC_RATE=150.0
```

### 1.6 Run tests

```bash
make test          # 45 tests, 80%+ coverage required
make lint          # ruff check + format
```

### 1.7 Start the proxy

Delete any `sovereign_proxy.db` left over from an older version — the schema has changed and `CREATE TABLE IF NOT EXISTS` won't migrate it:

```bash
rm -f sovereign_proxy.db
make serve
# or: uv run uvicorn level5.proxy.main:app --reload --host 0.0.0.0 --port 18515
```

The server creates a fresh database on startup.

### 1.8 End-to-end smoke test

In a second terminal, run the setup script. It registers an agent, seeds a balance, and writes a `proxy.env` file you can source.

```bash
make smoke-setup
# or: uv run python scripts/smoke_setup.py --proxy-url http://localhost:18515
```

Then source it and use Claude Code through the proxy:

```bash
source proxy.env

# Verify balance
curl -s "http://localhost:18515/proxy/${LEVEL5_API_TOKEN}/balance" | jq .

# Use Claude Code — all requests route through the proxy
claude "What is the capital of France?"

# Check revenue stats
curl -s http://localhost:18515/v1/admin/stats | jq .
```

### 1.9 Test the Liquid Mirror (on-chain deposit flow)

The Liquid Mirror polls `getProgramAccounts` via RPC and subscribes via WebSocket to detect on-chain deposits. The smoke test above seeds balances directly in SQLite (bypassing the chain). This section tests the real on-chain path against the local validator.

**Prerequisites:** The proxy must be running (`make serve`), the local validator must be running (`solana-test-validator`), and the contract must be deployed (step 1.4).

#### 1.9.1 Register an agent and note the deposit code

```bash
curl -s -X POST http://localhost:18515/v1/register | jq .
```

Save the `api_token` and `deposit_code` from the response.

#### 1.9.2 Create a deposit account and deposit SOL on-chain

Use the test deposit script to initialize a deposit account and deposit 1 SOL:

```bash
make test-deposit
# or: cd contracts/sovereign-contract && node ../../scripts/test_deposit.js
```

The script generates a fresh deposit keypair, initializes the account on-chain, and deposits 1 SOL (1,000,000,000 lamports). It uses `ANCHOR_PROVIDER_URL` and `ANCHOR_WALLET` from your Solana CLI config.

#### 1.9.3 Watch the mirror detect the deposit

The mirror polls every 5 seconds. Watch the proxy logs for sync messages:

```
Liquid Mirror starting | rpc=http://localhost:8899 | program=C4UAHo...
Synced XXXXXXXX [So111111]: 0 -> 1000000000 (+1000000000)
Auto-activated token XXXXXXXX for pubkey XXXXXXXX
```

If you don't see the log, the mirror may not have discovered the new account yet. It discovers accounts on startup and every poll cycle. You can restart the proxy to trigger a fresh discovery.

#### 1.9.4 Verify the balance appeared via the API

```bash
# Replace with your api_token from step 1.9.1
curl -s "http://localhost:18515/proxy/YOUR_API_TOKEN/balance" | jq .
```

Expected: a `balances` object containing `So11111111111111111111111111111111111111112` with the deposited amount.

#### 1.9.5 What to check if the mirror isn't working

| Symptom | Cause | Fix |
|---------|-------|-----|
| No accounts discovered | Contract not deployed or wrong program ID | Check `SOVEREIGN_CONTRACT_ADDRESS` in `.env` matches `declare_id!()` |
| Balance stays at 0 | Deposit account created but not discovered yet | Restart the proxy to trigger `_discover_accounts()` |
| WebSocket errors in logs | Local validator WS on different port | Confirm `HELIUS_WS_URL=ws://localhost:8900` |
| `Poll error, backing off` | RPC URL wrong | Confirm `HELIUS_RPC_URL=http://localhost:8899` |
| Token not auto-activated | No pending token matched | Ensure you called `/v1/register` before depositing |

---

## 2. Staging (public server + Solana devnet)

Staging uses a real server accessible over the internet, pointed at Solana devnet. Free devnet SOL, but real infrastructure. Good for integration testing with remote agents.

### 2.1 Provision a server

Any Linux VPS with at least 1 vCPU, 1 GB RAM, and 10 GB disk. Examples: Hetzner CX22, DigitalOcean Basic Droplet, AWS Lightsail.

SSH in and install prerequisites (see top of this file).

### 2.2 Deploy the contract to devnet

From your development machine (or the server):

```bash
solana config set --url devnet
solana airdrop 5                       # fund deployer wallet

cd contracts/sovereign-contract

# Update Anchor.toml for devnet
# Change [provider] cluster = "devnet"
anchor build
anchor deploy --provider.cluster devnet
```

Note the deployed program ID. It should remain `C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve` if you use the same keypair.

### 2.3 Clone and install on the server

```bash
git clone https://github.com/chris-gilbert/Level5 /opt/level5
cd /opt/level5
uv sync --all-groups
```

### 2.4 Configure environment

Create `/opt/level5/.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-XXXX
OPENAI_API_KEY=sk-XXXX                  # optional

# Helius devnet — sign up at https://www.helius.dev for a free API key
HELIUS_API_KEY=YOUR_HELIUS_KEY
HELIUS_RPC_URL=https://devnet.helius-rpc.com/?api-key=YOUR_HELIUS_KEY
HELIUS_WS_URL=wss://devnet.helius-rpc.com/?api-key=YOUR_HELIUS_KEY

SOLANA_RPC_URL=https://api.devnet.solana.com
SOVEREIGN_CONTRACT_ADDRESS=C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve

USDC_MINT=4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU
SOL_USDC_RATE=150.0
```

### 2.5 Create a systemd service

Create `/etc/systemd/system/level5.service`:

```ini
[Unit]
Description=Level5 Billing Proxy (Staging)
After=network.target

[Service]
Type=simple
User=level5
WorkingDirectory=/opt/level5
EnvironmentFile=/opt/level5/.env
ExecStart=/opt/level5/.venv/bin/uvicorn level5.proxy.main:app --host 127.0.0.1 --port 18515
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo useradd --system --no-create-home level5
sudo chown -R level5:level5 /opt/level5
sudo systemctl daemon-reload
sudo systemctl enable level5
sudo systemctl start level5
sudo systemctl status level5
```

### 2.6 Set up nginx reverse proxy with TLS

Install nginx and certbot:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Create `/etc/nginx/sites-available/level5`:

```nginx
server {
    listen 80;
    server_name staging.level5.cloud;

    location / {
        proxy_pass http://127.0.0.1:18515;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE streaming support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

Enable and get TLS:

```bash
sudo ln -s /etc/nginx/sites-available/level5 /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d staging.level5.cloud
```

### 2.7 DNS

Point `staging.level5.cloud` A record to the server's public IP.

### 2.8 Verify staging

```bash
curl https://staging.level5.cloud/health
# → {"status":"arena_ready","agent":"Level5"}

curl -X POST https://staging.level5.cloud/v1/register | jq .
# → {"api_token":"...","deposit_code":"...","base_url":"..."}
```

### 2.9 Test the Liquid Mirror on devnet

On devnet the mirror connects to Helius for both RPC polling and WebSocket subscriptions. This tests the real Helius integration.

#### 2.9.1 Register and deposit on devnet

```bash
# 1. Register
curl -s -X POST https://staging.level5.cloud/v1/register | jq .
# Save api_token and deposit_code

# 2. Fund your wallet on devnet
solana config set --url devnet
solana airdrop 2

# 3. Create a deposit account and deposit SOL
# Use the same Anchor script from section 1.9.2, but with:
#   solana config set --url devnet
# The contract must already be deployed to devnet (step 2.2).
```

#### 2.9.2 Verify the mirror synced

```bash
# Check server logs
sudo journalctl -u level5 --since "5 minutes ago" | grep -i "synced\|mirror\|activated"

# Check balance via API
curl -s "https://staging.level5.cloud/proxy/YOUR_API_TOKEN/balance" | jq .
```

The mirror should discover the deposit within one poll cycle (5 seconds) or instantly via the Helius WebSocket.

#### 2.9.3 Staging mirror troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No accounts discovered | Helius API key invalid or wrong cluster | Verify `HELIUS_API_KEY` and that URLs use `devnet` |
| WebSocket disconnects | Helius free tier rate limits | Check `journalctl` for backoff messages; upgrade Helius plan |
| Balance shows on-chain but not in API | Mirror hasn't polled yet | Wait 5 seconds or restart: `sudo systemctl restart level5` |
| `getProgramAccounts` returns empty | Contract deployed to wrong cluster | Confirm program exists: `solana program show C4UAHo... --url devnet` |

---

## 3. Production (public server + Solana mainnet-beta)

Production handles real money. Every configuration choice here is security-sensitive.

### 3.1 Server requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| vCPU | 2 | 4 |
| RAM | 2 GB | 4 GB |
| Disk | 20 GB SSD | 40 GB SSD |
| OS | Ubuntu 22.04+ | Ubuntu 24.04 LTS |

Use a provider with persistent disk (SQLite is the only state). Enable automated backups for the disk.

### 3.2 Deploy the contract to mainnet

**This costs real SOL.** Deploying an Anchor program to mainnet requires approximately 2-3 SOL for rent.

```bash
solana config set --url mainnet-beta

cd contracts/sovereign-contract

# Update Anchor.toml:
#   [provider]
#   cluster = "mainnet-beta"
#   wallet = "/path/to/your/mainnet-deployer-keypair.json"

anchor build
anchor deploy --provider.cluster mainnet-beta
```

Save the deployer keypair securely. You will need it for future program upgrades.

### 3.3 Configure environment

Create `/opt/level5/.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-XXXX
OPENAI_API_KEY=sk-XXXX

# Helius mainnet — paid plan recommended for production rate limits
HELIUS_API_KEY=YOUR_HELIUS_MAINNET_KEY
HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_HELIUS_MAINNET_KEY
HELIUS_WS_URL=wss://mainnet.helius-rpc.com/?api-key=YOUR_HELIUS_MAINNET_KEY

SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOVEREIGN_CONTRACT_ADDRESS=C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve

# Mainnet USDC mint address
USDC_MINT=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
SOL_USDC_RATE=150.0
```

**Critical differences from staging:**
- `USDC_MINT` changes to the mainnet USDC mint (`EPjFWdd5...`)
- `HELIUS_*_URL` endpoints use `mainnet` instead of `devnet`
- `SOL_USDC_RATE` should be updated regularly to reflect the real market rate

### 3.4 Harden the server

```bash
# Firewall — only allow SSH, HTTP, HTTPS
sudo ufw default deny incoming
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Disable root SSH login
sudo sed -i 's/^PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# File permissions — .env must not be world-readable
chmod 600 /opt/level5/.env
chown level5:level5 /opt/level5/.env

# Automatic security updates
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 3.5 Create the systemd service

Same as staging (section 2.5), but with production-appropriate limits:

```ini
[Unit]
Description=Level5 Billing Proxy (Production)
After=network.target

[Service]
Type=simple
User=level5
WorkingDirectory=/opt/level5
EnvironmentFile=/opt/level5/.env
ExecStart=/opt/level5/.venv/bin/uvicorn level5.proxy.main:app --host 127.0.0.1 --port 18515 --workers 2
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

Note `--workers 2` for production concurrency. SQLite with WAL mode handles concurrent reads well.

### 3.6 Set up nginx with TLS

Same as staging (section 2.6), but with `api.level5.cloud` as the server name:

```nginx
server {
    listen 80;
    server_name api.level5.cloud;

    location / {
        proxy_pass http://127.0.0.1:18515;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE streaming support — do not buffer
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

```bash
sudo certbot --nginx -d api.level5.cloud
```

### 3.7 DNS

Point `api.level5.cloud` A record to the production server's public IP.

### 3.8 Database backups

SQLite lives at `/opt/level5/sovereign_proxy.db`. Back it up:

```bash
# Add to crontab for the level5 user
# Runs every 6 hours, keeps 7 days of backups
0 */6 * * * sqlite3 /opt/level5/sovereign_proxy.db ".backup /opt/level5/backups/proxy-$(date +\%Y\%m\%d-\%H\%M).db" && find /opt/level5/backups -name "proxy-*.db" -mtime +7 -delete
```

```bash
sudo -u level5 mkdir -p /opt/level5/backups
```

### 3.9 Monitoring

Check the proxy is alive:

```bash
# Simple health check (add to cron or external uptime monitor)
curl -sf https://api.level5.cloud/health || echo "LEVEL5 DOWN"
```

Check logs:

```bash
sudo journalctl -u level5 -f            # live logs
sudo journalctl -u level5 --since today  # today's logs
```

### 3.10 Verify production

```bash
curl https://api.level5.cloud/health
curl https://api.level5.cloud/v1/pricing | jq .
curl -X POST https://api.level5.cloud/v1/register | jq .
curl https://api.level5.cloud/v1/admin/stats | jq .
```

### 3.11 Verify the Liquid Mirror on mainnet

On mainnet the mirror uses Helius mainnet RPC and WebSocket endpoints. **This involves real funds.**

#### 3.11.1 Confirm the mirror is connected

```bash
# Look for the startup log line
sudo journalctl -u level5 | grep "Liquid Mirror starting"
# Expected: Liquid Mirror starting | rpc=https://mainnet.helius-rpc.com | program=C4UAHo...

# Look for discovered accounts (if any deposits have already happened)
sudo journalctl -u level5 | grep "Discovered"
# Expected: Discovered N deposit accounts
```

#### 3.11.2 Test with a real deposit

```bash
# 1. Register
curl -s -X POST https://api.level5.cloud/v1/register | jq .

# 2. Deposit real SOL or USDC to the contract using the deposit code
# (Use a Solana wallet — Phantom, Solflare, or CLI)

# 3. Watch logs for the mirror to pick it up
sudo journalctl -u level5 -f | grep -i "synced\|activated"

# 4. Verify balance
curl -s "https://api.level5.cloud/proxy/YOUR_API_TOKEN/balance" | jq .
```

#### 3.11.3 Production mirror monitoring

Add these checks to your monitoring/alerting:

```bash
# Mirror health: check that the admin stats show active agents
# If deposits are happening but active_agents stays at 0, the mirror is broken
curl -sf https://api.level5.cloud/v1/admin/stats | jq '.active_agents'

# Check for mirror errors in the last hour
sudo journalctl -u level5 --since "1 hour ago" | grep -c "Poll error\|WebSocket error"
```

| Alert condition | Likely cause | Action |
|----------------|--------------|--------|
| Repeated `Poll error, backing off` | Helius rate limit or downtime | Check https://helius.statuspage.io; consider upgrading plan |
| `WebSocket error, reconnecting` loops | Helius WS connection dropped | Mirror auto-reconnects with backoff; check API key validity |
| Deposits on-chain but not in DB | Mirror not running or wrong program ID | `sudo systemctl status level5`; check `SOVEREIGN_CONTRACT_ADDRESS` |
| `active_agents` drops to 0 unexpectedly | DB corrupted or deleted | Restore from backup (section 3.8) |

---

## Updating a running deployment

For both staging and production:

```bash
cd /opt/level5
git pull origin main
uv sync
sudo systemctl restart level5
sudo systemctl status level5

# Verify
curl -sf https://YOUR_DOMAIN/health | jq .
```

For contract upgrades (requires the original deployer keypair):

```bash
cd contracts/sovereign-contract
anchor build
anchor upgrade --provider.cluster TARGET_CLUSTER --program-id C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve
```

---

## Environment comparison

| Setting | Local | Staging | Production |
|---------|-------|---------|------------|
| Solana cluster | localhost:8899 | devnet | mainnet-beta |
| USDC mint | devnet | devnet | `EPjFWdd5...` (mainnet) |
| Helius | not needed | free tier | paid plan |
| Domain | localhost:18515 | staging.level5.cloud | api.level5.cloud |
| TLS | no | yes (certbot) | yes (certbot) |
| Workers | 1 (reload) | 1 | 2+ |
| Backups | no | optional | required |
| Real funds | no | no (devnet SOL) | yes |
