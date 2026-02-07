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

```bash
make serve
# or: uv run uvicorn level5.proxy.main:app --reload --host 0.0.0.0 --port 8000
```

### 1.8 End-to-end smoke test

```bash
# Register
curl -s -X POST http://localhost:8000/v1/register | jq .

# Seed balance manually (no on-chain deposit needed for local dev)
uv run python -c "
from level5.proxy import database
database.init_db()
database.update_balance('test-pubkey', database.USDC_MINT, 10_000_000, 'MANUAL_SEED')
database.activate_token('YOUR_DEPOSIT_CODE', 'test-pubkey')
"

# Set env vars and use Claude Code through the proxy
export ANTHROPIC_BASE_URL=http://localhost:8000/proxy/YOUR_API_TOKEN
export ANTHROPIC_API_KEY=level5
claude "What is the capital of France?"

# Check balance
curl -s http://localhost:8000/proxy/YOUR_API_TOKEN/balance | jq .

# Check stats
curl -s http://localhost:8000/v1/admin/stats | jq .
```

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
ExecStart=/opt/level5/.venv/bin/uvicorn level5.proxy.main:app --host 127.0.0.1 --port 8000
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
        proxy_pass http://127.0.0.1:8000;
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
ExecStart=/opt/level5/.venv/bin/uvicorn level5.proxy.main:app --host 127.0.0.1 --port 8000 --workers 2
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
        proxy_pass http://127.0.0.1:8000;
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
| Domain | localhost:8000 | staging.level5.cloud | api.level5.cloud |
| TLS | no | yes (certbot) | yes (certbot) |
| Workers | 1 (reload) | 1 | 2+ |
| Backups | no | optional | required |
| Real funds | no | no (devnet SOL) | yes |
