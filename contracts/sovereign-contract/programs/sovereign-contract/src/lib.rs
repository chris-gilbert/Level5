use anchor_lang::prelude::*;

declare_id!("C4UAHoYgqZ7dmS4JypAwQcJ1YzYVM86S2eA1PTUthzve");

#[program]
pub mod sovereign_contract {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let deposit_account = &mut ctx.accounts.deposit_account;
        deposit_account.owner = *ctx.accounts.owner.key;
        deposit_account.balance = 0;
        msg!("Sovereign Deposit Account Initialized for: {:?}", deposit_account.owner);
        Ok(())
    }

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
            amount,
            new_balance: deposit_account.balance,
        });

        msg!("Deposit received: {} lamports. New balance: {}", amount, deposit_account.balance);
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(init, payer = owner, space = 8 + 32 + 8)]
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

#[account]
pub struct DepositAccount {
    pub owner: Pubkey,
    pub balance: u64,
}

#[event]
pub struct DepositEvent {
    pub owner: Pubkey,
    pub amount: u64,
    pub new_balance: u64,
}
