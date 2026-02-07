use anchor_lang::prelude::*;
use anchor_spl::associated_token::AssociatedToken;
use anchor_spl::token::{self, Mint, Token, TokenAccount, TransferChecked};

declare_id!("C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve");

#[program]
pub mod sovereign_contract {
    use super::*;

    /// Initialize a SOL deposit account (legacy, backward compatible).
    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let deposit_account = &mut ctx.accounts.deposit_account;
        deposit_account.owner = *ctx.accounts.owner.key;
        deposit_account.mint = System::id(); // Native SOL sentinel
        deposit_account.balance = 0;
        msg!(
            "SOL Deposit Account initialized for: {:?}",
            deposit_account.owner
        );
        Ok(())
    }

    /// Deposit native SOL into the deposit account.
    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        let ix = anchor_lang::solana_program::system_instruction::transfer(
            &ctx.accounts.owner.key(),
            &ctx.accounts.deposit_account.key(),
            amount,
        );
        anchor_lang::solana_program::program::invoke(
            &ix,
            &[
                ctx.accounts.owner.to_account_info(),
                ctx.accounts.deposit_account.to_account_info(),
            ],
        )?;

        let deposit_account = &mut ctx.accounts.deposit_account;
        deposit_account.balance += amount;

        emit!(DepositEvent {
            owner: *ctx.accounts.owner.key,
            mint: deposit_account.mint,
            amount,
            new_balance: deposit_account.balance,
        });

        msg!(
            "SOL deposit: {} lamports. Balance: {}",
            amount,
            deposit_account.balance
        );
        Ok(())
    }

    /// Withdraw native SOL from the deposit account back to the owner.
    pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
        let deposit_account = &mut ctx.accounts.deposit_account;
        require!(
            deposit_account.balance >= amount,
            SovereignError::InsufficientBalance
        );

        // Transfer SOL from deposit_account to recipient
        let deposit_info = deposit_account.to_account_info();
        let recipient_info = ctx.accounts.recipient.to_account_info();

        **deposit_info.try_borrow_mut_lamports()? -= amount;
        **recipient_info.try_borrow_mut_lamports()? += amount;

        deposit_account.balance -= amount;

        emit!(WithdrawEvent {
            owner: *ctx.accounts.owner.key,
            mint: deposit_account.mint,
            amount,
            new_balance: deposit_account.balance,
        });

        msg!(
            "SOL withdraw: {} lamports. Balance: {}",
            amount,
            deposit_account.balance
        );
        Ok(())
    }

    /// Initialize a token (e.g. USDC) deposit account.
    pub fn initialize_token(ctx: Context<InitializeToken>) -> Result<()> {
        let deposit_account = &mut ctx.accounts.deposit_account;
        deposit_account.owner = *ctx.accounts.owner.key;
        deposit_account.mint = ctx.accounts.mint.key();
        deposit_account.balance = 0;
        msg!(
            "Token Deposit Account initialized for: {:?} mint: {:?}",
            deposit_account.owner,
            deposit_account.mint
        );
        Ok(())
    }

    /// Deposit SPL tokens (e.g. USDC) into the deposit vault.
    pub fn deposit_token(ctx: Context<DepositToken>, amount: u64) -> Result<()> {
        let decimals = ctx.accounts.mint.decimals;

        let cpi_accounts = TransferChecked {
            from: ctx.accounts.user_token_account.to_account_info(),
            mint: ctx.accounts.mint.to_account_info(),
            to: ctx.accounts.vault_token_account.to_account_info(),
            authority: ctx.accounts.owner.to_account_info(),
        };
        let cpi_ctx = CpiContext::new(
            ctx.accounts.token_program.to_account_info(),
            cpi_accounts,
        );
        token::transfer_checked(cpi_ctx, amount, decimals)?;

        let deposit_account = &mut ctx.accounts.deposit_account;
        deposit_account.balance += amount;

        emit!(DepositEvent {
            owner: *ctx.accounts.owner.key,
            mint: deposit_account.mint,
            amount,
            new_balance: deposit_account.balance,
        });

        msg!(
            "Token deposit: {} units. Balance: {}",
            amount,
            deposit_account.balance
        );
        Ok(())
    }

    /// Withdraw SPL tokens from the deposit vault back to the owner.
    pub fn withdraw_token(ctx: Context<WithdrawToken>, amount: u64) -> Result<()> {
        let deposit_account = &mut ctx.accounts.deposit_account;
        require!(
            deposit_account.balance >= amount,
            SovereignError::InsufficientBalance
        );

        let decimals = ctx.accounts.mint.decimals;

        // PDA signer seeds: deposit_account is the vault authority
        let deposit_key = deposit_account.key();
        let seeds: &[&[u8]] = &[deposit_key.as_ref()];
        let (_, bump) = Pubkey::find_program_address(seeds, &crate::ID);
        let signer_seeds: &[&[&[u8]]] = &[&[deposit_key.as_ref(), &[bump]]];

        let cpi_accounts = TransferChecked {
            from: ctx.accounts.vault_token_account.to_account_info(),
            mint: ctx.accounts.mint.to_account_info(),
            to: ctx.accounts.recipient_token_account.to_account_info(),
            authority: deposit_account.to_account_info(),
        };
        let cpi_ctx = CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            cpi_accounts,
            signer_seeds,
        );
        token::transfer_checked(cpi_ctx, amount, decimals)?;

        deposit_account.balance -= amount;

        emit!(WithdrawEvent {
            owner: *ctx.accounts.owner.key,
            mint: deposit_account.mint,
            amount,
            new_balance: deposit_account.balance,
        });

        msg!(
            "Token withdraw: {} units. Balance: {}",
            amount,
            deposit_account.balance
        );
        Ok(())
    }
}

// ── Account structs ──────────────────────────────────────────────────

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(init, payer = owner, space = 8 + 32 + 32 + 8)]
    pub deposit_account: Account<'info, DepositAccount>,
    #[account(mut)]
    pub owner: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Deposit<'info> {
    #[account(mut, has_one = owner)]
    pub deposit_account: Account<'info, DepositAccount>,
    #[account(mut)]
    pub owner: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Withdraw<'info> {
    #[account(mut, has_one = owner)]
    pub deposit_account: Account<'info, DepositAccount>,
    #[account(mut)]
    pub owner: Signer<'info>,
    /// The recipient of the SOL withdrawal (can be the owner or another account).
    /// CHECK: Any valid system account can receive SOL.
    #[account(mut)]
    pub recipient: AccountInfo<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct InitializeToken<'info> {
    #[account(init, payer = owner, space = 8 + 32 + 32 + 8)]
    pub deposit_account: Account<'info, DepositAccount>,
    pub mint: Account<'info, Mint>,
    #[account(
        init,
        payer = owner,
        associated_token::mint = mint,
        associated_token::authority = deposit_account,
    )]
    pub vault_token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    pub owner: Signer<'info>,
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct DepositToken<'info> {
    #[account(mut, has_one = owner, constraint = deposit_account.mint == mint.key())]
    pub deposit_account: Account<'info, DepositAccount>,
    pub mint: Account<'info, Mint>,
    #[account(
        mut,
        associated_token::mint = mint,
        associated_token::authority = owner,
    )]
    pub user_token_account: Account<'info, TokenAccount>,
    #[account(
        mut,
        associated_token::mint = mint,
        associated_token::authority = deposit_account,
    )]
    pub vault_token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    pub owner: Signer<'info>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct WithdrawToken<'info> {
    #[account(mut, has_one = owner, constraint = deposit_account.mint == mint.key())]
    pub deposit_account: Account<'info, DepositAccount>,
    pub mint: Account<'info, Mint>,
    #[account(
        mut,
        associated_token::mint = mint,
        associated_token::authority = deposit_account,
    )]
    pub vault_token_account: Account<'info, TokenAccount>,
    /// The recipient token account for the withdrawal.
    #[account(
        mut,
        token::mint = mint,
    )]
    pub recipient_token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    pub owner: Signer<'info>,
    pub token_program: Program<'info, Token>,
}

// ── State ────────────────────────────────────────────────────────────

/// Deposit account tracking balance for a single token per owner.
/// Layout: discriminator(8) + owner(32) + mint(32) + balance(8) = 80 bytes
#[account]
pub struct DepositAccount {
    pub owner: Pubkey,
    pub mint: Pubkey,
    pub balance: u64,
}

// ── Events ───────────────────────────────────────────────────────────

#[event]
pub struct DepositEvent {
    pub owner: Pubkey,
    pub mint: Pubkey,
    pub amount: u64,
    pub new_balance: u64,
}

#[event]
pub struct WithdrawEvent {
    pub owner: Pubkey,
    pub mint: Pubkey,
    pub amount: u64,
    pub new_balance: u64,
}

// ── Errors ───────────────────────────────────────────────────────────

#[error_code]
pub enum SovereignError {
    #[msg("Insufficient balance for withdrawal")]
    InsufficientBalance,
}
