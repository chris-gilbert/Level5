/**
 * Initialize a deposit account and deposit 1 SOL into it on the local validator.
 *
 * Prerequisites:
 *   - solana-test-validator running
 *   - Contract deployed (anchor deploy --provider.cluster localnet)
 *   - Wallet funded (solana airdrop 10)
 *
 * Usage: node scripts/test_deposit.js <DEPOSIT_CODE>
 *   DEPOSIT_CODE: the 8-character code from /v1/register (e.g. "ABC123XY")
 *
 * Requires: @coral-xyz/anchor (installed via contracts/sovereign-contract/node_modules)
 */

const anchor = require("@coral-xyz/anchor");
const fs = require("fs");
const path = require("path");

async function main() {
  const depositCode = process.argv[2];
  if (!depositCode || depositCode.length !== 8) {
    console.error(
      "Usage: node scripts/test_deposit.js <DEPOSIT_CODE>\n" +
        "  DEPOSIT_CODE must be exactly 8 characters (from /v1/register)"
    );
    process.exit(1);
  }

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

  // Convert deposit code to 8-byte array
  const depositCodeBytes = Buffer.alloc(8);
  depositCodeBytes.write(depositCode, "utf8");

  // Derive the PDA for this deposit account
  const [depositAccountPDA] = anchor.web3.PublicKey.findProgramAddressSync(
    [
      Buffer.from("deposit"),
      depositCodeBytes,
      provider.wallet.publicKey.toBuffer(),
    ],
    program.programId
  );

  console.log("Deposit code:   ", depositCode);
  console.log("Deposit account:", depositAccountPDA.toBase58());
  console.log("Owner:          ", provider.wallet.publicKey.toBase58());

  // Initialize the deposit account with the deposit code
  await program.methods
    .initialize(Array.from(depositCodeBytes))
    .accounts({
      depositAccount: depositAccountPDA,
      owner: provider.wallet.publicKey,
    })
    .rpc();
  console.log("Initialized deposit account");

  // Deposit 1 SOL (1_000_000_000 lamports)
  const amount = new anchor.BN(1_000_000_000);
  await program.methods
    .deposit(amount)
    .accounts({
      depositAccount: depositAccountPDA,
      owner: provider.wallet.publicKey,
    })
    .rpc();
  console.log("Deposited 1 SOL (1,000,000,000 lamports)");
  console.log(
    "The Liquid Mirror should detect this within 30 seconds — check the proxy logs."
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
