/**
 * Initialize a deposit account and deposit 1 SOL into it on the local validator.
 *
 * Prerequisites:
 *   - solana-test-validator running
 *   - Contract deployed (anchor deploy --provider.cluster localnet)
 *   - Wallet funded (solana airdrop 10)
 *
 * Usage: node scripts/test_deposit.js
 *
 * Requires: @coral-xyz/anchor (installed via contracts/sovereign-contract/node_modules)
 */

const anchor = require("@coral-xyz/anchor");
const fs = require("fs");
const path = require("path");

async function main() {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const idlPath = path.join(
    __dirname,
    "..",
    "contracts",
    "sovereign-contract",
    "target",
    "idl",
    "sovereign_contract.json"
  );
  const idl = JSON.parse(fs.readFileSync(idlPath, "utf8"));
  const program = new anchor.Program(idl, provider);

  // Generate a fresh deposit account keypair
  const depositAccount = anchor.web3.Keypair.generate();
  console.log("Deposit account:", depositAccount.publicKey.toBase58());
  console.log("Owner:          ", provider.wallet.publicKey.toBase58());

  // Initialize the deposit account
  await program.methods
    .initialize()
    .accounts({
      depositAccount: depositAccount.publicKey,
      owner: provider.wallet.publicKey,
    })
    .signers([depositAccount])
    .rpc();
  console.log("Initialized deposit account");

  // Deposit 1 SOL (1_000_000_000 lamports)
  const amount = new anchor.BN(1_000_000_000);
  await program.methods
    .deposit(amount)
    .accounts({
      depositAccount: depositAccount.publicKey,
      owner: provider.wallet.publicKey,
    })
    .rpc();
  console.log("Deposited 1 SOL (1,000,000,000 lamports)");
  console.log(
    "The Liquid Mirror should detect this within 5 seconds — check the proxy logs."
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
