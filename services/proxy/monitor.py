import asyncio
import json
import os
from anchorpy import Program, Idl, Provider, Wallet
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from services.proxy import database
from dotenv import load_dotenv

load_dotenv()

IDL_PATH = "contracts/sovereign-contract/target/idl/sovereign_contract.json"
RPC_URL = os.getenv("SOLANA_RPC_URL")
PROGRAM_ID = os.getenv("SOVEREIGN_CONTRACT_ADDRESS")

async def main():
    # Load IDL
    with open(IDL_PATH, "r") as f:
        idl_json = f.read()
    idl = Idl.from_json(idl_json)

    # Setup connection and provider
    client = AsyncClient(RPC_URL)
    # Use a dummy wallet for monitoring (we only need the provider to listen)
    provider = Provider(client, Wallet.local())
    program = Program(idl, Pubkey.from_string(PROGRAM_ID), provider)

    print(f"Monitoring Sovereign Proxy deposits on {RPC_URL}...")
    print(f"Program ID: {PROGRAM_ID}")

    # Subscribe to DepositEvent
    # Note: anchorpy event listeners are async generators
    async for event in program.event_listener():
        if event.name == "DepositEvent":
            owner = str(event.data.owner)
            amount = event.data.amount
            new_balance = event.data.new_balance
            
            print(f"--- On-chain Deposit Detected ---")
            print(f"Agent: {owner}")
            print(f"Amount: {amount} lamports")
            print(f"Contract Balance: {new_balance} lamports")
            
            # Update local persistent store
            database.update_balance(owner, amount, "DEPOSIT")
            print(f"Local balance updated for {owner}")

if __name__ == "__main__":
    try:
        database.init_db()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Monitoring stopped.")
