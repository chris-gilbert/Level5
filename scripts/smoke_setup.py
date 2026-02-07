"""Register an agent, seed a local balance, and write proxy.env.

Usage: uv run python scripts/smoke_setup.py [--proxy-url URL]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from level5.proxy import database


def main() -> None:
    parser = argparse.ArgumentParser(description="Level5 local smoke-test setup")
    parser.add_argument(
        "--proxy-url",
        default="http://localhost:18515",
        help="Base URL of the running Level5 proxy (default: http://localhost:18515)",
    )
    args = parser.parse_args()
    base = args.proxy_url.rstrip("/")

    # 1. Register
    req = urllib.request.Request(f"{base}/v1/register", method="POST")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    api_token = data["api_token"]
    deposit_code = data["deposit_code"]
    print(f"api_token:    {api_token}")
    print(f"deposit_code: {deposit_code}")

    # 2. Seed balance directly in SQLite (bypasses on-chain deposit)
    database.init_db()
    database.update_balance("local-dev-agent", database.USDC_MINT, 10_000_000, "MANUAL_SEED")
    database.activate_token(deposit_code, "local-dev-agent")
    print("Balance seeded: 10 USDC")

    # 3. Write sourceable env file
    Path("proxy.env").write_text(
        f"export ANTHROPIC_BASE_URL={base}/proxy/{api_token}\n"
        "export ANTHROPIC_API_KEY=level5\n"
        f"export LEVEL5_API_TOKEN={api_token}\n"
    )
    print("Wrote proxy.env — run: source proxy.env")


if __name__ == "__main__":
    main()
